from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


# ── Auth Schemas ──────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="customer", pattern="^(customer|agent)$")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Category Schemas ──────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class CategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str]

    class Config:
        from_attributes = True


# ── Ticket Schemas ────────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    category_id: Optional[int] = None


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    description: Optional[str] = Field(None, min_length=10)
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    category_id: Optional[int] = None


class TicketStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|in_progress|resolved)$")


class TicketAssign(BaseModel):
    agent_id: int


class CommentOut(BaseModel):
    id: int
    content: str
    user_id: int
    author_name: Optional[str] = None
    author_role: Optional[str] = None
    is_ai_generated: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    status: str
    priority: str
    customer_id: int
    customer_name: Optional[str] = None
    agent_id: Optional[int] = None
    agent_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    comments: List[CommentOut] = []

    class Config:
        from_attributes = True


class TicketListOut(BaseModel):
    id: int
    title: str
    status: str
    priority: str
    customer_id: int
    customer_name: Optional[str] = None
    agent_id: Optional[int] = None
    agent_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    comment_count: int = 0

    class Config:
        from_attributes = True


# ── Comment Schemas ───────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)


# ── AI Suggestion Schema ─────────────────────────────────────

class AISuggestRequest(BaseModel):
    ticket_id: int


class AISuggestResponse(BaseModel):
    suggestion: str
    method: str  # "template" or "ai"


# ── Dashboard Stats ──────────────────────────────────────────

class DashboardStats(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    my_tickets: Optional[int] = None


# ── Semantic Similarity Schemas ───────────────────────────────

class SimilarTicketOut(BaseModel):
    id: int
    title: str
    status: str
    priority: str
    similarity_score: float   # cosine similarity in [−1, 1]; practically [0, 1]
    customer_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SimilarTicketsResponse(BaseModel):
    results: List[SimilarTicketOut]
    method: str  # "semantic" | "unavailable"
    suggested_priority: Optional[str] = None    # weighted k-NN vote
    priority_confidence: Optional[float] = None # fraction of vote weight [0,1]
