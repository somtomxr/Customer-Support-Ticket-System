from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Ticket
from schemas import SimilarTicketsResponse, SimilarTicketOut
from auth import get_current_user
from models import User
import similarity_engine

router = APIRouter(prefix="/api/tickets", tags=["Similar Tickets"])


@router.get("/{ticket_id}/similar", response_model=SimilarTicketsResponse)
def get_similar_tickets(
    ticket_id: int,
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the top_k semantically similar tickets to the given ticket.

    Uses sentence-transformers (all-MiniLM-L6-v2) to embed ticket text into
    384-dimensional vectors, then ranks all other tickets by cosine similarity.

    Embeddings are cached in-memory and persisted to the DB (BLOB column) so
    repeated queries are fast (<50ms) after the first computation.

    Returns method='unavailable' if the ML model is not installed.
    """
    # Fetch the query ticket
    query_ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.customer))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not query_ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Customers can only search from their own tickets
    if current_user.role == "customer" and query_ticket.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if ML engine is available
    if not similarity_engine.is_available():
        return SimilarTicketsResponse(results=[], method="unavailable")

    # Load tickets for comparison.
    # SECURITY: customers may only match against their own tickets —
    # they must never receive data belonging to other customers.
    # Agents see all tickets (needed for cross-customer pattern matching).
    ticket_query = db.query(Ticket).options(joinedload(Ticket.customer))
    if current_user.role == "customer":
        ticket_query = ticket_query.filter(Ticket.customer_id == current_user.id)
    all_tickets = ticket_query.all()

    # Run semantic similarity search
    similar = similarity_engine.find_similar(
        query_ticket=query_ticket,
        all_tickets=all_tickets,
        db=db,
        top_k=top_k,
    )

    results = [
        SimilarTicketOut(
            id=ticket.id,
            title=ticket.title,
            status=ticket.status,
            priority=ticket.priority,
            similarity_score=round(score, 4),
            customer_name=ticket.customer.name if ticket.customer else None,
            created_at=ticket.created_at,
        )
        for ticket, score in similar
    ]

    # Weighted k-NN priority vote — free, reuses already-computed similar list
    suggested_priority, priority_confidence = similarity_engine.suggest_priority(similar)

    return SimilarTicketsResponse(
        results=results,
        method="semantic",
        suggested_priority=suggested_priority,
        priority_confidence=priority_confidence,
    )
