"""
similarity_engine.py
====================
Singleton embedding engine for semantic ticket search.

Architecture Design Decisions:
- Model: all-MiniLM-L6-v2 via fastembed (ONNX runtime, ~150MB RAM, no PyTorch)
  Identical 384-dim embeddings to sentence-transformers but fits free-tier hosting.
- Search: brute-force NumPy cosine similarity — O(n), fine for <10k tickets
- Cache: in-memory dict {ticket_id → ndarray}; also persisted to DB BLOB column
  so cold-start skips recomputation (Redis-ready interface for production)
- Invalidation: call invalidate(ticket_id) on ticket create/update to keep
  cache coherent — prevents stale embeddings being served after edits

Scale & Optimization Paths:
- Swap NumPy cosine loop for faiss.IndexFlatIP for O(log n) ANN at 10k+ tickets
- Replace in-memory cache with Redis HSET for multi-worker deployments
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from models import Ticket

logger = logging.getLogger(__name__)

# ── Model loading ──────────────────────────────────────────────────────────────

import threading

_model = None          # fastembed TextEmbedding instance (loaded once)
_available = None      # bool | None  (None = not yet checked)
_model_lock = threading.Lock()

# In-memory cache: ticket_id → 384-dim float32 ndarray
# Acts as L1 cache in front of the DB BLOB column (L2).
_embedding_cache: dict[int, np.ndarray] = {}


def _get_model():
    """Load the model exactly once (lazy singleton). Thread-safe using lock."""
    global _model, _available
    if _available is not None:
        return _model  # already resolved

    with _model_lock:
        # Double-check inside lock
        if _available is not None:
            return _model

        try:
            from fastembed import TextEmbedding
            logger.info("Loading fastembed model: all-MiniLM-L6-v2 (ONNX, no PyTorch) …")
            _model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
            _available = True
            logger.info("Embedding model loaded ✓")
        except ImportError:
            logger.warning(
                "fastembed not installed. "
                "Semantic search will be unavailable. "
                "Run: pip install fastembed"
            )
            _available = False
        except Exception as exc:
            logger.error("Failed to load embedding model: %s", exc)
            _available = False

        return _model


def is_available() -> bool:
    """Return True if the embedding model loaded successfully."""
    _get_model()
    return bool(_available)


# ── Serialisation helpers ──────────────────────────────────────────────────────

def _ndarray_to_bytes(arr: np.ndarray) -> bytes:
    """Pack a float32 ndarray into raw bytes for BLOB storage."""
    return struct.pack(f"{len(arr)}f", *arr.astype(np.float32))


def _bytes_to_ndarray(blob: bytes) -> np.ndarray:
    """Unpack BLOB bytes back to a float32 ndarray."""
    n = len(blob) // 4  # 4 bytes per float32
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


# ── Embedding computation + cache ──────────────────────────────────────────────

def _ticket_text(ticket: "Ticket") -> str:
    """Concatenate title + description as the embedding input."""
    return f"{ticket.title}. {ticket.description}"


def _get_or_compute_embedding(ticket: "Ticket", db: "Session") -> Optional[np.ndarray]:
    """
    Return the embedding for a ticket with a 3-level strategy:
      1. In-memory cache (fastest)
      2. DB BLOB column (fast, survives restart)
      3. Compute with sentence-transformers, then persist to both
    """
    model = _get_model()
    if not _available:
        return None

    # L1: in-memory cache
    if ticket.id in _embedding_cache:
        return _embedding_cache[ticket.id]

    # L2: DB BLOB (persisted across restarts)
    if ticket.embedding is not None:
        emb = _bytes_to_ndarray(ticket.embedding)
        _embedding_cache[ticket.id] = emb
        return emb

    # L3: compute fresh via fastembed (returns a generator of np.ndarray)
    text = _ticket_text(ticket)
    emb = next(iter(model.embed([text]))).astype(np.float32)

    # Persist to DB
    ticket.embedding = _ndarray_to_bytes(emb)
    db.add(ticket)
    db.commit()

    # Populate in-memory cache
    _embedding_cache[ticket.id] = emb
    return emb


def invalidate(ticket_id: int) -> None:
    """
    Evict a ticket's embedding from the in-memory cache.
    Call this whenever a ticket's title or description changes so the
    next similarity query forces a fresh encode + DB persist.
    """
    _embedding_cache.pop(ticket_id, None)


def prewarm_all(db: "Session") -> None:
    """
    Pre-compute and cache embeddings for every ticket in the database.

    Called once at server startup so the in-memory cache is fully populated
    before any user request arrives.  Without this, the first call to
    find_similar() on a cold-started server blocks for 60+ seconds while
    it encodes all 120+ tickets one by one.

    After this runs, every subsequent find_similar() call hits only the
    in-memory cache and completes in milliseconds.
    """
    if not is_available():
        logger.warning("Embedding model unavailable — skipping pre-warm.")
        return

    from models import Ticket  # local import to avoid circular dependency at module level

    tickets = db.query(Ticket).all()
    total = len(tickets)
    if total == 0:
        logger.info("No tickets in DB — nothing to pre-warm.")
        return

    logger.info("Pre-warming embeddings for %d tickets …", total)
    cached = 0
    computed = 0

    for ticket in tickets:
        already_in_memory = ticket.id in _embedding_cache
        already_in_db = ticket.embedding is not None

        if already_in_memory:
            cached += 1
            continue  # already warm, skip

        # This call populates both the in-memory cache and the DB BLOB if missing
        _get_or_compute_embedding(ticket, db)

        if already_in_db:
            cached += 1   # loaded from DB blob (fast)
        else:
            computed += 1  # freshly encoded by model (slow, but done once)

    logger.info(
        "Pre-warm complete: %d from DB cache, %d freshly computed, %d total.",
        cached, computed, total,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def find_similar(
    query_ticket: "Ticket",
    all_tickets: list["Ticket"],
    db: "Session",
    top_k: int = 5,
) -> list[tuple["Ticket", float]]:
    """
    Find the top_k tickets most semantically similar to query_ticket.

    Algorithm:
      - Encode query_ticket text → q_vec (384-dim)
      - For each candidate (excluding query_ticket itself) get its embedding
      - cosine_similarity = dot(q, c) / (||q|| * ||c||)  ∈ [−1, 1]
      - Return top_k sorted descending, as (ticket, score) pairs

    Complexity: O(n * d) where n=# tickets, d=384 (embedding dim)
    Suitable for <10k tickets; swap NumPy loop for FAISS at scale.
    """
    if not is_available():
        return []

    q_emb = _get_or_compute_embedding(query_ticket, db)
    if q_emb is None:
        return []

    # Normalise query vector once
    q_norm = q_emb / (np.linalg.norm(q_emb) + 1e-10)

    scores: list[tuple["Ticket", float]] = []

    for ticket in all_tickets:
        if ticket.id == query_ticket.id:
            continue  # skip self

        c_emb = _get_or_compute_embedding(ticket, db)
        if c_emb is None:
            continue

        # Cosine similarity via dot product of unit vectors
        c_norm = c_emb / (np.linalg.norm(c_emb) + 1e-10)
        similarity = float(np.dot(q_norm, c_norm))
        scores.append((ticket, similarity))

    # Sort descending by similarity score
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def suggest_priority(
    similar: list[tuple["Ticket", float]],
) -> tuple[str, float] | tuple[None, None]:
    """
    Predict priority for a new ticket using squared-weight k-NN voting.

    Each similar ticket casts a vote for its own priority, weighted by the
    SQUARE of its cosine similarity score.  Squaring amplifies the signal
    from the closest neighbours and suppresses noise from distant, weakly-
    similar tickets, improving discrimination between priority classes.

    Returns (priority_label, confidence_0_to_1) or (None, None) if no data.

    Example:
        similar = [(ticket_urgent, 0.91), (ticket_medium, 0.83), (ticket_low, 0.41)]
        weights = {urgent: 0.91²=0.828, medium: 0.83²=0.689, low: 0.41²=0.168}
        winner  = urgent  (confidence = 0.828 / (0.828+0.689+0.168) = 0.49)
    """
    if not similar:
        return None, None

    # Accumulate squared-similarity votes per priority
    votes: dict[str, float] = {}
    for ticket, score in similar:
        p = ticket.priority
        votes[p] = votes.get(p, 0.0) + score ** 2   # ← squared weight

    total = sum(votes.values())
    if total == 0:
        return None, None

    winner = max(votes, key=lambda p: votes[p])
    confidence = round(votes[winner] / total, 3)  # normalised [0, 1]
    return winner, confidence
