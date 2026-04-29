from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="customer")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tickets_created = relationship(
        "Ticket", back_populates="customer",
        foreign_keys="Ticket.customer_id"
    )
    tickets_assigned = relationship(
        "Ticket", back_populates="agent",
        foreign_keys="Ticket.agent_id"
    )
    comments = relationship("Comment", back_populates="author")

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500), nullable=True)

    tickets = relationship("Ticket", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_priority", "priority"),
        Index("ix_tickets_customer_id", "customer_id"),
        Index("ix_tickets_agent_id", "agent_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), default="open", nullable=False)
    priority = Column(String(20), default="medium", nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = relationship(
        "User", back_populates="tickets_created",
        foreign_keys=[customer_id]
    )
    agent = relationship(
        "User", back_populates="tickets_assigned",
        foreign_keys=[agent_id]
    )
    category = relationship("Category", back_populates="tickets")
    comments = relationship(
        "Comment", back_populates="ticket",
        order_by="Comment.created_at",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Ticket #{self.id}: {self.title[:30]}>"


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_ai_generated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User", back_populates="comments")

    def __repr__(self):
        return f"<Comment #{self.id} on Ticket #{self.ticket_id}>"
