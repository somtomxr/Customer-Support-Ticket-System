#!/usr/bin/env python3
"""
scripts/train_priority_classifier.py
======================================
Standalone script to fine-tune DistilBERT as a 3-class priority classifier.

NOT imported by the server — run manually:
    cd backend
    python scripts/train_priority_classifier.py

Classes:
    0 = low
    1 = medium
    2 = urgent

Output: ./models/priority-distilbert/

After running, the server automatically detects and loads the model at startup
via similarity_engine.load_priority_classifier().

Requirements (installed in Phase 5):
    transformers>=4.35.0
    torch>=2.0.0
    datasets>=2.0.0

Usage:
    GROQ_API_KEY=gsk_... python scripts/train_priority_classifier.py
    # or without API key (uses existing ticket priorities, skips auto-labelling)
    python scripts/train_priority_classifier.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# ── Add backend/ to sys.path ──────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_MODEL = "distilbert-base-uncased"
OUTPUT_PATH = os.path.join(_BACKEND_DIR, "models", "priority-distilbert")
LABEL2ID = {"low": 0, "medium": 1, "urgent": 2}
ID2LABEL = {0: "low", 1: "medium", 2: "urgent"}
BATCH_SIZE_GPT = 20
TRAIN_SPLIT = 0.8
EPOCHS = 3
TRAIN_BATCH = 16
EVAL_BATCH = 32


# ── DB access ─────────────────────────────────────────────────────────────────

def load_tickets() -> list[dict[str, Any]]:
    """Load all tickets from the SQLite DB."""
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
            }
            for t in tickets
        ]
    finally:
        db.close()


# ── GPT auto-labelling ────────────────────────────────────────────────────────

def _groq_request(prompt: str, api_key: str) -> str:
    import httpx
    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 0.0,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def auto_label_tickets(tickets: list[dict], api_key: str) -> list[dict]:
    """
    Use Groq (free) to assign a priority label to tickets that are missing one
    or have an unexpected value. Batches of BATCH_SIZE_GPT.

    Returns the ticket list with `.priority` normalised to low/medium/urgent.
    """
    valid_priorities = set(LABEL2ID.keys())

    # Tickets that need labelling
    to_label = [
        t for t in tickets if t["priority"] not in valid_priorities
    ]
    already_labelled = [
        t for t in tickets if t["priority"] in valid_priorities
    ]

    if not to_label:
        logger.info("All %d tickets already have valid priority labels.", len(tickets))
        return tickets

    logger.info(
        "%d tickets need auto-labelling (priorities not in %s).",
        len(to_label), valid_priorities,
    )

    labelled: dict[int, str] = {}
    for i in range(0, len(to_label), BATCH_SIZE_GPT):
        batch = to_label[i : i + BATCH_SIZE_GPT]
        ticket_texts = "\n".join(
            f"{j+1}. [{t['id']}] {t['title']}: {t['description'][:120]}"
            for j, t in enumerate(batch)
        )

        prompt = f"""You are a support ticket prioritisation expert.
Label each ticket with exactly one priority: "low", "medium", or "urgent".

Tickets:
{ticket_texts}

Return ONLY a JSON array matching the order above. Example:
[{{"ticket_id": 42, "priority": "medium"}}, ...]

Rules:
- urgent: data loss, security breach, system down, payment failed
- medium: degraded functionality, non-critical errors
- low: feature requests, cosmetic issues, general questions

Return ONLY the JSON array, no explanation."""

        try:
            raw = _groq_request(prompt, api_key)
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            results = json.loads(raw)
            for item in results:
                tid = item.get("ticket_id")
                priority = item.get("priority", "").lower()
                if tid and priority in valid_priorities:
                    labelled[tid] = priority
            logger.info(
                "Auto-label batch %d/%d — labelled %d tickets.",
                i // BATCH_SIZE_GPT + 1,
                (len(to_label) + BATCH_SIZE_GPT - 1) // BATCH_SIZE_GPT,
                len(results),
            )
        except Exception as exc:
            logger.warning("Groq labelling batch %d failed: %s", i // BATCH_SIZE_GPT + 1, exc)

    # Apply labels
    for t in to_label:
        if t["id"] in labelled:
            t["priority"] = labelled[t["id"]]
        else:
            t["priority"] = "medium"  # safe default if GPT failed

    return already_labelled + to_label


# ── Training ──────────────────────────────────────────────────────────────────

def train(tickets: list[dict]) -> None:
    """Fine-tune DistilBERT as a 3-class priority classifier."""
    import random
    import numpy as np
    import torch
    from datasets import Dataset
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
        DataCollatorWithPadding,
    )
    from sklearn.metrics import classification_report

    valid = [t for t in tickets if t["priority"] in LABEL2ID]
    if len(valid) < 10:
        logger.error(
            "Need at least 10 labelled tickets (got %d). Exiting.", len(valid)
        )
        sys.exit(1)

    logger.info("Training on %d labelled tickets.", len(valid))

    # Shuffle and split
    random.shuffle(valid)
    split = int(len(valid) * TRAIN_SPLIT)
    train_data = valid[:split]
    val_data = valid[split:] if split < len(valid) else valid[-max(1, len(valid)//5):]

    logger.info("Train: %d | Val: %d", len(train_data), len(val_data))

    def make_dataset(rows: list[dict]) -> Dataset:
        return Dataset.from_dict({
            "text": [f"{r['title']} {r['description']}" for r in rows],
            "label": [LABEL2ID[r["priority"]] for r in rows],
        })

    train_ds = make_dataset(train_data)
    val_ds = make_dataset(val_data)

    logger.info("Loading tokenizer: %s …", BASE_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=256,
            padding=False,
        )

    train_ds = train_ds.map(tokenize, batched=True, remove_columns=["text"])
    val_ds = val_ds.map(tokenize, batched=True, remove_columns=["text"])

    logger.info("Loading model: %s …", BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        acc = (preds == labels).mean()
        return {"accuracy": float(acc)}

    os.makedirs(OUTPUT_PATH, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=OUTPUT_PATH,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=TRAIN_BATCH,
        per_device_eval_batch_size=EVAL_BATCH,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_steps=10,
        report_to="none",    # no wandb/tensorboard
        fp16=False,  # fp16 not supported on Apple MPS; use bfloat16 on M-series if needed
    )

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,   # renamed from 'tokenizer' in transformers v5
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    logger.info("Fine-tuning DistilBERT for %d epoch(s) …", EPOCHS)
    trainer.train()

    # Save final model + tokenizer
    trainer.save_model(OUTPUT_PATH)
    tokenizer.save_pretrained(OUTPUT_PATH)
    logger.info("Model saved to: %s", OUTPUT_PATH)

    # ── Classification report on validation split ──────────────────────────
    logger.info("=== Validation Classification Report ===")
    val_preds_output = trainer.predict(val_ds)
    val_preds = np.argmax(val_preds_output.predictions, axis=-1)
    val_labels = val_preds_output.label_ids

    # Use sklearn if available, otherwise print raw counts
    try:
        from sklearn.metrics import classification_report as cr
        report = cr(
            val_labels,
            val_preds,
            target_names=list(LABEL2ID.keys()),
            zero_division=0,
        )
        logger.info("\n%s", report)
    except ImportError:
        from collections import Counter
        correct = (val_preds == val_labels).sum()
        total = len(val_labels)
        logger.info("Accuracy: %.3f (%d/%d)", correct / total, correct, total)
        pred_counts = Counter(val_preds.tolist())
        logger.info("Prediction distribution: %s", {ID2LABEL[k]: v for k, v in pred_counts.items()})

    logger.info(
        "Done. The server will auto-load the classifier on next startup from: %s",
        OUTPUT_PATH,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

    api_key = os.getenv("GROQ_API_KEY", "").strip()

    logger.info("Loading tickets from DB …")
    tickets = load_tickets()
    logger.info("Loaded %d tickets.", len(tickets))

    if len(tickets) < 10:
        logger.error("Need at least 10 tickets to train. Exiting.")
        sys.exit(1)

    # Auto-label tickets that lack a valid priority
    if api_key:
        tickets = auto_label_tickets(tickets, api_key)
    else:
        logger.info(
            "No GROQ_API_KEY — skipping auto-labelling. "
            "Using existing ticket priorities (tickets with invalid priorities will be skipped)."
        )

    train(tickets)


if __name__ == "__main__":
    main()
