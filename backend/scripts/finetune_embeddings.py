#!/usr/bin/env python3
"""
scripts/finetune_embeddings.py
==============================
Standalone script to fine-tune all-MiniLM-L6-v2 on your ticket corpus.

NOT imported by the server — run manually:
    cd backend
    python scripts/finetune_embeddings.py

Output: ./models/ticket-minilm-finetuned/

After running, set EMBEDDING_MODEL_PATH=./models/ticket-minilm-finetuned/
in your .env file to make the server use the fine-tuned checkpoint.

Requirements (installed separately from the server):
    sentence-transformers>=2.2.0
    datasets>=2.0.0
    openai or httpx (for GPT pair generation)

Usage:
    GROQ_API_KEY=gsk_... python scripts/finetune_embeddings.py
"""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from typing import Any

# ── Add backend/ to sys.path so we can import database.py and models.py ──────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OUTPUT_PATH = os.path.join(_BACKEND_DIR, "models", "ticket-minilm-finetuned")
BATCH_SIZE_GPT = 20        # tickets per GPT call
POSITIVE_PAIRS = 10        # positive pairs requested per batch
NEGATIVE_PAIRS = 5         # negative pairs requested per batch
HELD_OUT_PAIRS = 10        # pairs kept for before/after evaluation
EPOCHS = 1


# ── DB access ─────────────────────────────────────────────────────────────────

def load_tickets() -> list[dict[str, Any]]:
    """Load all tickets from the SQLite DB using the server's SQLAlchemy config."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

    from database import SessionLocal
    from models import Ticket

    db = SessionLocal()
    try:
        tickets = db.query(Ticket).all()
        return [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "priority": t.priority,
                "status": t.status,
            }
            for t in tickets
        ]
    finally:
        db.close()


# ── GPT pair generation ───────────────────────────────────────────────────────

def _groq_request(prompt: str, api_key: str) -> str:
    """Send a single chat completion request to Groq (free) and return the text."""
    import httpx

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "temperature": 0.5,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def generate_pairs_groq(
    tickets: list[dict], api_key: str
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """
    Call Groq (free) in batches of BATCH_SIZE_GPT tickets.

    Returns:
        positives: list of (text_a, text_b) semantically similar pairs
        negatives: list of (text_a, text_b) semantically dissimilar pairs
    """
    positives: list[tuple[str, str]] = []
    negatives: list[tuple[str, str]] = []

    for i in range(0, len(tickets), BATCH_SIZE_GPT):
        batch = tickets[i : i + BATCH_SIZE_GPT]
        ticket_texts = "\n".join(
            f"{j+1}. [{t['id']}] {t['title']}: {t['description'][:120]}"
            for j, t in enumerate(batch)
        )

        prompt = f"""You are a data labeller for a semantic similarity model.
Given these support tickets, generate training pairs.

Tickets:
{ticket_texts}

Return ONLY a JSON object with two arrays:
- "positives": {POSITIVE_PAIRS} pairs of (index_a, index_b) that are semantically SIMILAR
- "negatives": {NEGATIVE_PAIRS} pairs of (index_a, index_b) that are semantically DIFFERENT

Use 1-based indices matching the list above. Example:
{{"positives": [[1,3],[2,5]], "negatives": [[1,4],[2,6]]}}

Return ONLY the JSON, no explanation."""

        try:
            raw = _groq_request(prompt, api_key)
            # Strip markdown code fences if present
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)

            def _idx_to_text(idx: int) -> str:
                t = batch[idx - 1]
                return f"{t['title']}. {t['description']}"

            for a, b in data.get("positives", []):
                if 1 <= a <= len(batch) and 1 <= b <= len(batch) and a != b:
                    positives.append((_idx_to_text(a), _idx_to_text(b)))

            for a, b in data.get("negatives", []):
                if 1 <= a <= len(batch) and 1 <= b <= len(batch) and a != b:
                    negatives.append((_idx_to_text(a), _idx_to_text(b)))

            logger.info(
                "Batch %d/%d — %d pos, %d neg pairs generated.",
                i // BATCH_SIZE_GPT + 1,
                (len(tickets) + BATCH_SIZE_GPT - 1) // BATCH_SIZE_GPT,
                len(data.get("positives", [])),
                len(data.get("negatives", [])),
            )
        except Exception as exc:
            logger.warning("Groq batch %d failed, skipping: %s", i // BATCH_SIZE_GPT + 1, exc)

    return positives, negatives


def generate_pairs_heuristic(
    tickets: list[dict],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """
    Fallback pair generation without GPT.
    Positives: same-priority tickets (likely similar in urgency/type).
    Negatives: cross-priority tickets (likely different).
    """
    from collections import defaultdict

    by_priority: dict[str, list[dict]] = defaultdict(list)
    for t in tickets:
        by_priority[t["priority"]].append(t)

    def text(t: dict) -> str:
        return f"{t['title']}. {t['description']}"

    positives: list[tuple[str, str]] = []
    negatives: list[tuple[str, str]] = []

    for priority, group in by_priority.items():
        random.shuffle(group)
        for i in range(min(len(group) - 1, POSITIVE_PAIRS * 2)):
            positives.append((text(group[i]), text(group[i + 1])))

    priority_keys = list(by_priority.keys())
    for i in range(min(len(tickets) // 2, NEGATIVE_PAIRS * 4)):
        p1, p2 = random.sample(priority_keys, 2)
        if by_priority[p1] and by_priority[p2]:
            negatives.append(
                (text(random.choice(by_priority[p1])), text(random.choice(by_priority[p2])))
            )

    return positives[:50], negatives[:25]


# ── Fine-tuning ───────────────────────────────────────────────────────────────

def finetune(positives: list[tuple[str, str]], negatives: list[tuple[str, str]]) -> None:
    """Fine-tune all-MiniLM-L6-v2 with MultipleNegativesRankingLoss."""
    from sentence_transformers import SentenceTransformer, InputExample, losses
    from torch.utils.data import DataLoader

    if not positives:
        logger.error("No positive pairs — cannot fine-tune. Exiting.")
        sys.exit(1)

    logger.info("Loading base model: %s …", BASE_MODEL)
    model = SentenceTransformer(BASE_MODEL)

    # Build held-out sample for before/after comparison
    held_out = positives[:HELD_OUT_PAIRS]
    train_positives = positives[HELD_OUT_PAIRS:]

    # Before fine-tuning: baseline cosine similarity on held-out pairs
    logger.info("=== Before fine-tuning ===")
    _print_similarity(model, held_out)

    # Build training set: positives only (MNRL implicitly treats in-batch as negatives)
    train_examples = [InputExample(texts=[a, b]) for a, b in train_positives]
    # Also add explicit negatives as hard negatives via InputExample triplets
    for pos_a, pos_b in train_positives[:len(negatives)]:
        neg_b_candidates = [b for a, b in negatives if a != pos_a]
        if neg_b_candidates:
            train_examples.append(InputExample(texts=[pos_a, pos_b, random.choice(neg_b_candidates)]))

    loader = DataLoader(train_examples, shuffle=True, batch_size=16)
    loss = losses.MultipleNegativesRankingLoss(model)

    logger.info(
        "Fine-tuning for %d epoch(s) on %d training examples …", EPOCHS, len(train_examples)
    )
    model.fit(
        train_objectives=[(loader, loss)],
        epochs=EPOCHS,
        warmup_steps=max(1, len(loader) // 10),
        show_progress_bar=True,
    )

    # After fine-tuning: compare similarity on held-out pairs
    logger.info("=== After fine-tuning ===")
    _print_similarity(model, held_out)

    os.makedirs(OUTPUT_PATH, exist_ok=True)
    model.save(OUTPUT_PATH)
    logger.info("Fine-tuned model saved to: %s", OUTPUT_PATH)
    logger.info(
        "Set EMBEDDING_MODEL_PATH=%s in your .env to activate it.", OUTPUT_PATH
    )


def _print_similarity(model: Any, pairs: list[tuple[str, str]]) -> None:
    """Print cosine similarity for a held-out set of pairs."""
    import numpy as np

    if not pairs:
        return

    texts_a = [a for a, _ in pairs]
    texts_b = [b for _, b in pairs]
    emb_a = model.encode(texts_a, convert_to_numpy=True, normalize_embeddings=True)
    emb_b = model.encode(texts_b, convert_to_numpy=True, normalize_embeddings=True)
    sims = (emb_a * emb_b).sum(axis=1)
    logger.info("  Mean cosine similarity on %d held-out pairs: %.4f", len(pairs), sims.mean())
    for i, ((a, b), sim) in enumerate(zip(pairs[:3], sims[:3])):
        logger.info("  Pair %d: %.4f | %s ... <-> %s ...", i + 1, sim, a[:50], b[:50])


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

    api_key = os.getenv("GROQ_API_KEY", "").strip()

    logger.info("Loading tickets from DB …")
    tickets = load_tickets()
    logger.info("Loaded %d tickets.", len(tickets))

    if len(tickets) < 4:
        logger.error("Need at least 4 tickets to generate pairs. Exiting.")
        sys.exit(1)

    if api_key:
        logger.info("Generating pairs via Groq Llama 3.3 70B (free, batch size=%d) …", BATCH_SIZE_GPT)
        positives, negatives = generate_pairs_groq(tickets, api_key)
    else:
        logger.warning("No GROQ_API_KEY — using heuristic pair generation.")
        positives, negatives = generate_pairs_heuristic(tickets)

    logger.info("Total pairs — positives: %d, negatives: %d", len(positives), len(negatives))

    finetune(positives, negatives)


if __name__ == "__main__":
    main()
