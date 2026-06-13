from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from database import get_db
from models import User, Ticket, Comment, Category
from schemas import (
    TicketCreate, TicketUpdate, TicketOut, TicketListOut,
    TicketStatusUpdate, TicketAssign, DashboardStats
)
from auth import get_current_user, require_role
import similarity_engine

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])


def _serialize_ticket_list(ticket, comment_count=0):
    return TicketListOut(
        id=ticket.id,
        title=ticket.title,
        status=ticket.status,
        priority=ticket.priority,
        customer_id=ticket.customer_id,
        customer_name=ticket.customer.name if ticket.customer else None,
        agent_id=ticket.agent_id,
        agent_name=ticket.agent.name if ticket.agent else None,
        category_name=ticket.category.name if ticket.category else None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        comment_count=comment_count,
    )


def _serialize_ticket_detail(ticket):
    return TicketOut(
        id=ticket.id,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        customer_id=ticket.customer_id,
        customer_name=ticket.customer.name if ticket.customer else None,
        agent_id=ticket.agent_id,
        agent_name=ticket.agent.name if ticket.agent else None,
        category_id=ticket.category_id,
        category_name=ticket.category.name if ticket.category else None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        comments=[
            {
                "id": c.id,
                "content": c.content,
                "user_id": c.user_id,
                "author_name": c.author.name if c.author else None,
                "author_role": c.author.role if c.author else None,
                "is_ai_generated": c.is_ai_generated,
                "created_at": c.created_at,
            }
            for c in ticket.comments
        ],
    )


@router.get("/", response_model=list[TicketListOut])
def list_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List tickets. Customers see only their own tickets.
    Agents see all tickets.
    """
    query = db.query(Ticket).options(
        joinedload(Ticket.customer),
        joinedload(Ticket.agent),
        joinedload(Ticket.category),
    )

    # Role-based filtering
    if current_user.role == "customer":
        query = query.filter(Ticket.customer_id == current_user.id)

    # Apply filters
    if status_filter:
        query = query.filter(Ticket.status == status_filter)
    if priority:
        query = query.filter(Ticket.priority == priority)
    if category_id:
        query = query.filter(Ticket.category_id == category_id)
    if search:
        query = query.filter(
            Ticket.title.ilike(f"%{search}%") | Ticket.description.ilike(f"%{search}%")
        )

    # Pagination
    query = query.order_by(Ticket.created_at.desc())
    tickets = query.offset((page - 1) * limit).limit(limit).all()

    # Get comment counts
    comment_counts = {}
    if tickets:
        ticket_ids = [t.id for t in tickets]
        counts = (
            db.query(Comment.ticket_id, func.count(Comment.id))
            .filter(Comment.ticket_id.in_(ticket_ids))
            .group_by(Comment.ticket_id)
            .all()
        )
        comment_counts = dict(counts)

    return [
        _serialize_ticket_list(t, comment_counts.get(t.id, 0))
        for t in tickets
    ]


@router.post("/", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new support ticket (any authenticated user)."""
    if payload.category_id:
        category = db.query(Category).filter(Category.id == payload.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

    ticket = Ticket(
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        category_id=payload.category_id,
        customer_id=current_user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Reload relationships
    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.agent),
            joinedload(Ticket.category),
            joinedload(Ticket.comments),
        )
        .filter(Ticket.id == ticket.id)
        .first()
    )
    # New ticket — no cached embedding yet, but invalidate defensively
    similarity_engine.invalidate(ticket.id)
    return _serialize_ticket_detail(ticket)


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard statistics."""
    base_query = db.query(Ticket)

    if current_user.role == "customer":
        base_query = base_query.filter(Ticket.customer_id == current_user.id)

    total = base_query.count()
    open_count = base_query.filter(Ticket.status == "open").count()
    in_progress = base_query.filter(Ticket.status == "in_progress").count()
    resolved = base_query.filter(Ticket.status == "resolved").count()

    my_tickets = None
    if current_user.role == "agent":
        my_tickets = base_query.filter(Ticket.agent_id == current_user.id).count()

    return DashboardStats(
        total_tickets=total,
        open_tickets=open_count,
        in_progress_tickets=in_progress,
        resolved_tickets=resolved,
        my_tickets=my_tickets,
    )


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get ticket details with comments."""
    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.agent),
            joinedload(Ticket.category),
            joinedload(Ticket.comments).joinedload(Comment.author),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Customers can only view their own tickets
    if current_user.role == "customer" and ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return _serialize_ticket_detail(ticket)


@router.put("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update ticket details (title, description, priority, category)."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if current_user.role == "customer" and ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ticket, key, value)

    db.commit()
    db.refresh(ticket)

    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.agent),
            joinedload(Ticket.category),
            joinedload(Ticket.comments).joinedload(Comment.author),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    # Title/description may have changed — evict stale embedding from cache
    similarity_engine.invalidate(ticket_id)
    return _serialize_ticket_detail(ticket)


@router.patch("/{ticket_id}/status", response_model=TicketOut)
def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update ticket status (Open → In Progress → Resolved)."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Validate status transitions
    valid_transitions = {
        "open": ["in_progress", "resolved"],
        "in_progress": ["open", "resolved"],
        "resolved": ["open"],
    }

    if payload.status not in valid_transitions.get(ticket.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{ticket.status}' to '{payload.status}'"
        )

    ticket.status = payload.status
    db.commit()
    db.refresh(ticket)

    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.agent),
            joinedload(Ticket.category),
            joinedload(Ticket.comments).joinedload(Comment.author),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    return _serialize_ticket_detail(ticket)


@router.patch("/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(
    ticket_id: int,
    payload: TicketAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["agent"])),
):
    """Assign a ticket to an agent (agents only)."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    agent = db.query(User).filter(
        User.id == payload.agent_id, User.role == "agent"
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    ticket.agent_id = payload.agent_id
    if ticket.status == "open":
        ticket.status = "in_progress"

    db.commit()
    db.refresh(ticket)

    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.agent),
            joinedload(Ticket.category),
            joinedload(Ticket.comments).joinedload(Comment.author),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    return _serialize_ticket_detail(ticket)
