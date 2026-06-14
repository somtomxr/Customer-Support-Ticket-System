import os
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from database import engine, Base, SessionLocal
from routers import auth_routes, tickets, comments, categories, users, ai_suggest, similar_tickets
import similarity_engine

load_dotenv()

logger = logging.getLogger(__name__)


def _background_prewarm() -> None:
    """
    Pre-warm all ticket embeddings in a background thread.

    Runs after the server is already accepting requests, so:
      - Render marks the deploy as 'Live' immediately (no 50s wait)
      - Embeddings are fully cached within ~30-40 seconds of boot
      - Any /similar request that arrives before prewarm finishes falls back
        to on-demand encoding for that one ticket only (still much faster
        than the old 60s wait for all 120 tickets at once)
    """
    db = SessionLocal()
    try:
        logger.info("Background pre-warm started …")
        similarity_engine.prewarm_all(db)
        logger.info("Background pre-warm complete — all embeddings cached.")
    except Exception as exc:
        logger.error("Background pre-warm failed (non-fatal): %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler — runs once on startup.

    Startup sequence:
      1. Create DB tables (safe to run on every boot)
      2. Load the fastembed ONNX model into RAM (~10-15 sec)
      3. Kick off embedding pre-warm in a background thread
      4. yield → server opens port immediately, Render marks deploy 'Live'
      5. Background thread finishes caching all embeddings within ~30-40 sec
    """
    # Step 1: ensure DB schema is up to date
    Base.metadata.create_all(bind=engine)

    # Step 2: load model weights synchronously (must finish before serving)
    logger.info("Loading embedding model …")
    similarity_engine.is_available()
    logger.info("Embedding model ready.")

    # Step 3: launch pre-warm as a daemon thread so it doesn't block startup
    if similarity_engine.is_available():
        t = threading.Thread(target=_background_prewarm, daemon=True, name="prewarm")
        t.start()
    else:
        logger.warning("Embedding model not available — pre-warm skipped.")

    # Step 4: open the port — Render marks deploy 'Live' here
    logger.info("Server ready — accepting requests (pre-warm running in background).")
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
