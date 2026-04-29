from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserOut
from auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/agents", response_model=list[UserOut])
def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all available agents (for ticket assignment)."""
    agents = (
        db.query(User)
        .filter(User.role == "agent", User.is_active == True)
        .order_by(User.name)
        .all()
    )
    return agents
