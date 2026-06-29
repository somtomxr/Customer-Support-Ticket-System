"""
similarity_engine.py
====================
Singleton embedding engine for semantic ticket search.

Architecture Design Decisions:
- Model: all-MiniLM-L6-v2 via fastembed (ONNX runtime, ~150MB RAM, no PyTorch)
  Identical 384-dim embeddings to sentence-transformers but fits free-tier hosting.
  Override with EMBEDDING_MODEL_PATH env var to use a fine-tuned checkpoint.
- Search: Qdrant in-process vector DB (`:memory:` by default).
  Swap to remote Qdrant by setting QDRANT_URL env var.
  search() replaces the O(n) NumPy loop with Qdrant's ANN index.
- Cold-start bootstrap: SQLite LargeBinary column is kept as L2 backup.
  On first start (Qdrant collection empty) all stored BLOBs are batch-upserted.
- Invalidation: call invalidate(ticket_id) on ticket create/update to keep
  the Qdrant collection coherent — prevents stale embeddings being served.

Scale & Optimization Paths:
- Set QDRANT_URL to a remote Qdrant instance for persistent, multi-worker search
- Replace ":memory:" with a path string for on-disk local persistence
"""

from __future__ import annotations

import logging
import os
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
            # Phase 4: honour EMBEDDING_MODEL_PATH for fine-tuned checkpoints.
            # Use `or` fallback because os.getenv returns "" (not None) when the
            # var is set to an empty string in .env — the default= arg won't help.
            model_name = (
                os.getenv("EMBEDDING_MODEL_PATH", "").strip()
                or "sentence-transformers/all-MiniLM-L6-v2"
            )
            logger.info("Loading fastembed model: %s (ONNX, no PyTorch) …", model_name)
            _model = TextEmbedding(model_name)
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


# ── Qdrant client (in-process or remote) ──────────────────────────────────────

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PointIdsList

_COLLECTION = "tickets"
_VECTOR_SIZE = 384

_qdrant_client: Optional[QdrantClient] = None
_qdrant_lock = threading.Lock()


def _get_qdrant() -> QdrantClient:
    """Return the Qdrant client singleton, initialising it on first call."""
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client

    with _qdrant_lock:
        if _qdrant_client is not None:
            return _qdrant_client

        qdrant_url = os.getenv("QDRANT_URL", "").strip()
        if qdrant_url:
            logger.info("Connecting to remote Qdrant at %s …", qdrant_url)
            _qdrant_client = QdrantClient(url=qdrant_url)
        else:
            logger.info("Initialising in-process Qdrant (:memory:) …")
            _qdrant_client = QdrantClient(":memory:")

        # Create collection if it doesn't exist yet
        existing = [c.name for c in _qdrant_client.get_collections().collections]
        if _COLLECTION not in existing:
            _qdrant_client.create_collection(
                collection_name=_COLLECTION,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Qdrant collection '%s' created.", _COLLECTION)

        return _qdrant_client


# ── Serialisation helpers (kept for SQLite BLOB read/write) ───────────────────

def _ndarray_to_bytes(arr: np.ndarray) -> bytes:
    """Pack a float32 ndarray into raw bytes for BLOB storage."""
    return struct.pack(f"{len(arr)}f", *arr.astype(np.float32))


def _bytes_to_ndarray(blob: bytes) -> np.ndarray:
    """Unpack BLOB bytes back to a float32 ndarray."""
    n = len(blob) // 4  # 4 bytes per float32
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


# ── Embedding computation + Qdrant upsert ─────────────────────────────────────

def _ticket_text(ticket: "Ticket") -> str:
    """Concatenate title + description as the embedding input."""
    return f"{ticket.title}. {ticket.description}"


def _upsert_to_qdrant(ticket: "Ticket", emb: np.ndarray) -> None:
    """Insert or update a single ticket vector in Qdrant."""
    client = _get_qdrant()
    client.upsert(
        collection_name=_COLLECTION,
        points=[
            PointStruct(
                id=ticket.id,
                vector=emb.tolist(),
                payload={
                    "ticket_id": ticket.id,
                    "title": ticket.title,
                    "priority": ticket.priority,
                    "status": ticket.status,
                },
            )
        ],
    )


def _get_or_compute_embedding(ticket: "Ticket", db: "Session") -> Optional[np.ndarray]:
    """
    Return the embedding for a ticket with a 3-level strategy:
      1. Qdrant collection (vector DB — fast, survives within process lifetime)
      2. SQLite BLOB column (fast, survives restart; bootstraps Qdrant on cold start)
      3. Compute with fastembed, then persist to both
    """
    model = _get_model()
    if not _available:
        return None

    client = _get_qdrant()

    # L1: Qdrant (in-memory or remote)
    existing = client.retrieve(
        collection_name=_COLLECTION,
        ids=[ticket.id],
        with_vectors=True,
    )
    if existing and existing[0].vector is not None:
        return np.array(existing[0].vector, dtype=np.float32)

    # L2: SQLite BLOB (persisted across restarts)
    if ticket.embedding is not None:
        emb = _bytes_to_ndarray(ticket.embedding)
        _upsert_to_qdrant(ticket, emb)
        return emb

    # L3: compute fresh via fastembed
    text = _ticket_text(ticket)
    emb = next(iter(model.embed([text]))).astype(np.float32)

    # Persist to SQLite BLOB
    ticket.embedding = _ndarray_to_bytes(emb)
    db.add(ticket)
    db.commit()

    # Upsert into Qdrant
    _upsert_to_qdrant(ticket, emb)

    return emb


def invalidate(ticket_id: int) -> None:
    """
    Evict a ticket's embedding from Qdrant.
    Call this whenever a ticket's title or description changes so the
    next similarity query forces a fresh encode + re-persist.
    """
    try:
        client = _get_qdrant()
        client.delete(
            collection_name=_COLLECTION,
            points_selector=PointIdsList(points=[ticket_id]),
        )
    except Exception as exc:
        logger.warning("Failed to invalidate ticket %d from Qdrant: %s", ticket_id, exc)


def prewarm_all(db: "Session") -> None:
    """
    Pre-compute and cache embeddings for every ticket in the database.

    Strategy:
      - If the Qdrant collection already has points (e.g. remote persistent),
        skip upsert — just verify the count.
      - If Qdrant is empty but SQLite has BLOB embeddings, batch-upsert them
        all in a single call (fast, no model inference needed).
      - Compute fresh embeddings for tickets missing both Qdrant and BLOB.

    Called once at server startup in a background thread.
    """
    if not is_available():
        logger.warning("Embedding model unavailable — skipping pre-warm.")
        return

    from models import Ticket  # local import to avoid circular at module level

    tickets = db.query(Ticket).all()
    total = len(tickets)
    if total == 0:
        logger.info("No tickets in DB — nothing to pre-warm.")
        return

    client = _get_qdrant()
    collection_count = client.count(collection_name=_COLLECTION).count

    logger.info(
        "Pre-warming: %d tickets in DB, %d already in Qdrant …",
        total, collection_count,
    )

    # Batch-upsert tickets that have a SQLite BLOB but are not yet in Qdrant
    blob_points: list[PointStruct] = []
    compute_tickets: list[Ticket] = []

    # Build set of ids already in Qdrant for fast membership check
    existing_ids: set[int] = set()
    if collection_count > 0:
        # Scroll through all existing points to get their IDs
        scroll_result = client.scroll(
            collection_name=_COLLECTION,
            limit=10_000,
            with_vectors=False,
        )
        for point in scroll_result[0]:
            existing_ids.add(int(point.id))

    for ticket in tickets:
        if ticket.id in existing_ids:
            continue  # already in Qdrant, skip

        if ticket.embedding is not None:
            emb = _bytes_to_ndarray(ticket.embedding)
            blob_points.append(
                PointStruct(
                    id=ticket.id,
                    vector=emb.tolist(),
                    payload={
                        "ticket_id": ticket.id,
                        "title": ticket.title,
                        "priority": ticket.priority,
                        "status": ticket.status,
                    },
                )
            )
        else:
            compute_tickets.append(ticket)

    # Batch upsert from SQLite BLOBs
    if blob_points:
        client.upsert(collection_name=_COLLECTION, points=blob_points)
        logger.info("Pre-warm: upserted %d from SQLite BLOBs.", len(blob_points))

    # Compute fresh for tickets missing BLOB
    freshly_computed = 0
    model = _get_model()
    for ticket in compute_tickets:
        text = _ticket_text(ticket)
        emb = next(iter(model.embed([text]))).astype(np.float32)

        ticket.embedding = _ndarray_to_bytes(emb)
        db.add(ticket)

        _upsert_to_qdrant(ticket, emb)
        freshly_computed += 1

    if compute_tickets:
        db.commit()

    logger.info(
        "Pre-warm complete: %d from Qdrant cache, %d from SQLite BLOB, "
        "%d freshly computed, %d total.",
        len(existing_ids), len(blob_points), freshly_computed, total,
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

    Algorithm (Phase 2):
      - Encode query_ticket text → q_vec (384-dim) via fastembed
      - qdrant_client.search() performs ANN cosine similarity in the collection
      - Map returned point IDs back to Ticket ORM objects via all_tickets lookup
      - Returns (ticket, score) pairs sorted descending by cosine similarity

    all_tickets is passed to allow role-based filtering by the caller
    (customers only match their own tickets). The Qdrant search is performed
    on the full collection, then filtered client-side against all_tickets ids.
    """
    if not is_available():
        return []

    q_emb = _get_or_compute_embedding(query_ticket, db)
    if q_emb is None:
        return []

    client = _get_qdrant()

    # Build a set of allowed ticket IDs (role-based access already applied by caller)
    allowed_ids: set[int] = {t.id for t in all_tickets}

    # Search Qdrant — request more than top_k to account for self + filtered-out ids
    # Uses query_points() (qdrant-client >= 1.7, replaces deprecated search())
    search_limit = min(top_k + 20, 100)
    response = client.query_points(
        collection_name=_COLLECTION,
        query=q_emb.tolist(),
        limit=search_limit,
        with_payload=True,
    )

    # Build id → Ticket map for O(1) lookup
    ticket_map: dict[int, "Ticket"] = {t.id: t for t in all_tickets}

    scores: list[tuple["Ticket", float]] = []
    for hit in response.points:
        hit_id = int(hit.id)
        if hit_id == query_ticket.id:
            continue  # skip self
        if hit_id not in allowed_ids:
            continue  # outside caller's visibility scope
        ticket = ticket_map.get(hit_id)
        if ticket is None:
            continue
        scores.append((ticket, float(hit.score)))
        if len(scores) >= top_k:
            break

    return scores


def suggest_priority(
    similar: list[tuple["Ticket", float]],
    ticket: Optional["Ticket"] = None,
) -> tuple[str, float] | tuple[None, None]:
    """
    Predict priority for a new ticket.

    Phase 5 path (when _priority_clf is loaded):
      Run DistilBERT text-classification inference on ticket.title + description.
      Returns (predicted_label, softmax_confidence).

    Default k-NN path (classifier not available or ticket not provided):
      Squared-weight k-NN vote over the similar tickets list.
      Each similar ticket casts a vote for its own priority weighted by score².
      Squaring amplifies the signal from the closest neighbours.
      Returns (priority_label, confidence_0_to_1) or (None, None) if no data.

    Return type is identical in both paths: tuple[str, float] | tuple[None, None]
    """
    # Phase 5: classifier path (loaded when ./models/priority-distilbert/ exists)
    if _priority_clf is not None and ticket is not None:
        try:
            text = f"{ticket.title} {ticket.description}"
            clf_result = _priority_clf(text, truncation=True, max_length=512)[0]
            label = clf_result["label"]   # e.g. "LABEL_0" → mapped below
            score = round(float(clf_result["score"]), 3)

            # Map HuggingFace LABEL_N back to priority strings
            _label_map = {"LABEL_0": "low", "LABEL_1": "medium", "LABEL_2": "urgent"}
            priority = _label_map.get(label, label.lower())
            return priority, score
        except Exception as exc:
            logger.warning("Priority classifier inference failed, falling back to k-NN: %s", exc)

    # Default k-NN vote (unchanged from original implementation)
    if not similar:
        return None, None

    votes: dict[str, float] = {}
    for t, score in similar:
        p = t.priority
        votes[p] = votes.get(p, 0.0) + score ** 2   # squared weight

    total = sum(votes.values())
    if total == 0:
        return None, None

    winner = max(votes, key=lambda p: votes[p])
    confidence = round(votes[winner] / total, 3)
    return winner, confidence


# ── Phase 5: Priority classifier singleton ────────────────────────────────────

def load_priority_classifier():
    """
    Load the fine-tuned DistilBERT priority classifier.

    Priority order:
    1. Local ./models/priority-distilbert/ directory (fastest, no network)
    2. HuggingFace Hub via HF_MODEL_ID env var (e.g. 'somtomxr/ticket-priority-distilbert')
    3. Returns None → falls back to k-NN priority prediction

    The model is trained by scripts/train_priority_classifier.py.
    Set HF_MODEL_ID in .env to enable live 94% accuracy on cloud deployments.
    """
    from transformers import pipeline

    # ── Path 1: local model folder ─────────────────────────────────────────────
    model_path = os.path.join(
        os.path.dirname(__file__), "models", "priority-distilbert"
    )
    if os.path.isdir(model_path):
        try:
            clf = pipeline(
                "text-classification",
                model=model_path,
                return_all_scores=False,
            )
            logger.info("Priority classifier loaded from local path ✓")
            return clf
        except Exception as exc:
            logger.warning("Failed to load local priority classifier: %s", exc)

    # ── Path 2: HuggingFace Hub ────────────────────────────────────────────────
    hf_model_id = os.getenv("HF_MODEL_ID", "").strip()
    if hf_model_id:
        try:
            logger.info("Downloading priority classifier from HF Hub: %s …", hf_model_id)
            clf = pipeline(
                "text-classification",
                model=hf_model_id,
                return_all_scores=False,
            )
            logger.info("Priority classifier loaded from HuggingFace Hub ✓ (%s)", hf_model_id)
            return clf
        except Exception as exc:
            logger.warning("Failed to load classifier from HF Hub (%s): %s", hf_model_id, exc)

    logger.info("No priority classifier found — using k-NN fallback.")
    return None


# Load once at module import
_priority_clf = load_priority_classifier()

