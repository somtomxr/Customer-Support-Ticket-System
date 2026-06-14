import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import engine, Base, SessionLocal
from routers import auth_routes, tickets, comments, categories, users, ai_suggest, similar_tickets
import similarity_engine

load_dotenv()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler — runs once at startup before any request is served.

    Startup sequence:
      1. Create DB tables (idempotent, safe to run every boot)
      2. Load the fastembed ONNX model into RAM (~10-15 sec on cold start)
      3. Pre-warm ALL ticket embeddings so the first /similar request is instant
         instead of making the first user wait 60+ seconds for on-demand encoding.

    Without step 3, a cold-started server encodes 120+ tickets one-by-one on the
    first /similar call — this moves that cost to startup where no user sees it.
    """
    # Step 1: ensure all DB tables exist
    Base.metadata.create_all(bind=engine)

    # Step 2: load the AI model (blocks until model weights are in RAM)
    logger.info("Loading embedding model …")
    similarity_engine.is_available()

    # Step 3: pre-warm all embeddings — server is ready only after this finishes
    if similarity_engine.is_available():
        db = SessionLocal()
        try:
            logger.info("Starting embedding pre-warm …")
            similarity_engine.prewarm_all(db)
        except Exception as exc:
            # Never crash the server over pre-warming — log and move on
            logger.error("Embedding pre-warm failed (non-fatal): %s", exc)
        finally:
            db.close()
    else:
        logger.warning("Embedding model not available — pre-warm skipped.")

    logger.info("Server startup complete — ready to serve requests.")
    yield
    # (nothing to clean up on shutdown)


app = FastAPI(
    title="Customer Support Ticket System",
    description=(
        "A full-stack support ticketing platform with role-based access, "
        "ticket lifecycle management, and AI-assisted reply suggestions."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
    """
    Lightweight health probe — used by uptime monitors to keep the server warm.
    Hit this endpoint every 10 minutes (e.g. via cron-job.org) to prevent
    Render's free-tier spin-down and eliminate cold-start delays for real users.
    """
    return {"status": "healthy"}
