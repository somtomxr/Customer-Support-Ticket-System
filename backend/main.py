import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import engine, Base
from routers import auth_routes, tickets, comments, categories, users, ai_suggest, similar_tickets

load_dotenv()

# Create all tables on startup
Base.metadata.create_all(bind=engine)

# Pre-warm the semantic similarity engine (downloads & loads ONNX model weights on boot)
import similarity_engine
similarity_engine.is_available()

app = FastAPI(
    title="Customer Support Ticket System",
    description="A full-stack support ticketing platform with role-based access, "
                "ticket lifecycle management, and AI-assisted reply suggestions.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
origins = [origin.strip() for origin in frontend_url.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router)
app.include_router(tickets.router)
app.include_router(comments.router)
app.include_router(categories.router)
app.include_router(users.router)
app.include_router(ai_suggest.router)
app.include_router(similar_tickets.router)


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Customer Support Ticket System API",
        "docs": "/docs",
        "version": "1.0.0",
    }


@app.get("/health", tags=["Root"])
def health_check():
    return {"status": "healthy"}
