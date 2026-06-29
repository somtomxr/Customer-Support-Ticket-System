# System Architecture

## Overview

The Semantic Ticket Retrieval & Priority Prediction System is a full-stack AI-powered
customer support platform. Version 2.0 adds a complete ML intelligence layer on top of
the existing FastAPI + React foundation.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                            │
│              (Vite · localhost:5173 · JWT auth)                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / REST
┌───────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend                              │
│                    (Uvicorn · port 8000)                         │
│                                                                  │
│  /api/tickets        /api/auth         /api/similar-tickets      │
│  /api/ai/suggest     /api/categories   /api/comments             │
└──────┬──────────────────────┬──────────────────────────────────┘
       │                      │
       ▼                      ▼
┌─────────────┐    ┌──────────────────────────────────────────────┐
│   SQLite    │    │         similarity_engine.py                  │
│  (tickets,  │    │  (singleton, thread-safe lazy loading)        │
│   users,    │    │                                               │
│   comments) │    │  ┌───────────────┐  ┌────────────────────┐  │
└─────────────┘    │  │ fastembed     │  │  Qdrant            │  │
                   │  │ MiniLM-L6-v2  │  │  (:memory:)        │  │
                   │  │ (ONNX, no GPU)│  │  HNSW vector index │  │
                   │  │ fine-tuned ✓  │  │  + payload filter  │  │
                   │  └───────┬───────┘  └────────┬───────────┘  │
                   │          │ embed               │ query_points │
                   │          └──────────┬──────────┘             │
                   │                     │                         │
                   │  ┌──────────────────▼───────────────────┐    │
                   │  │   DistilBERT Priority Classifier      │    │
                   │  │   (94% accuracy · low/med/urgent)     │    │
                   │  │   softmax confidence score returned   │    │
                   │  └──────────────────────────────────────┘    │
                   └──────────────────────────────────────────────┘
                                      │
                                      │ RAG context (resolved tickets)
                                      ▼
                   ┌──────────────────────────────────────────────┐
                   │        routers/ai_suggest.py                  │
                   │                                               │
                   │  LangChain LCEL Chain:                        │
                   │  ChatPromptTemplate | ChatGroq | StrOutput    │
                   │                                               │
                   │  ┌──────────┐    ┌──────────────────────┐   │
                   │  │  Groq    │    │  OpenAI (fallback)    │   │
                   │  │ Llama 3.3│    │  GPT-3.5-turbo        │   │
                   │  │  70B     │    │  (if key present)     │   │
                   │  │  FREE ✓  │    └──────────────────────┘   │
                   │  └──────────┘                                 │
                   │              ↓ if no key                       │
                   │  ┌──────────────────────┐                    │
                   │  │  Static Templates    │                    │
                   │  │  (always available)  │                    │
                   │  └──────────────────────┘                    │
                   └──────────────────────────────────────────────┘
```

---

## Request Flow — AI Reply Suggestion

```
POST /api/ai/suggest-reply/{ticket_id}
        │
        ▼
1. Load ticket from SQLite
        │
        ▼
2. Embed ticket text → fastembed MiniLM (fine-tuned)
        │
        ▼
3. Query Qdrant for top-3 RESOLVED similar tickets
        │
        ├── Found? → Build RAG context from their last agent comments
        │
        ▼
4. Build LangChain prompt:
   "Here are similar resolved tickets: {context}
    Now write a reply for: {ticket}"
        │
        ▼
5. Invoke Groq (Llama 3.3 70B) via LangChain
        │
        ├── Success → return suggestion, method="rag"
        ├── No context → method="llm_only"
        └── No key → method="template"
```

---

## Request Flow — Similar Ticket Search + Priority Prediction

```
GET /api/similar-tickets/{ticket_id}
        │
        ▼
1. Embed ticket text → fastembed MiniLM
        │
        ▼
2. Qdrant query_points() — cosine similarity, top-5
        │
        ▼
3a. Priority: DistilBERT classifier (if model loaded)
    → returns label + softmax confidence
3b. Priority fallback: weighted k-NN vote on similar ticket priorities
        │
        ▼
4. Return: similar_tickets[], suggested_priority, priority_confidence
```

---

## Component Map

| Component | File | Technology |
|---|---|---|
| API server | `main.py` | FastAPI + Uvicorn |
| Auth | `auth.py`, `routers/auth_routes.py` | JWT + bcrypt |
| Ticket CRUD | `routers/tickets.py` | SQLAlchemy + SQLite |
| ML core | `similarity_engine.py` | Qdrant + fastembed + DistilBERT |
| AI replies | `routers/ai_suggest.py` | LangChain LCEL + Groq |
| Similar search | `routers/similar_tickets.py` | similarity_engine singleton |
| Embedding fine-tune | `scripts/finetune_embeddings.py` | sentence-transformers + Groq |
| Classifier training | `scripts/train_priority_classifier.py` | HuggingFace Trainer + DistilBERT |
| Data import | `scripts/import_synthetic_tickets.py` | SQLAlchemy direct insert |
| Frontend | `frontend/src/` | React 18 + Vite |

---

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | ✅ | SQLite path |
| `SECRET_KEY` | ✅ | JWT signing key |
| `GROQ_API_KEY` | ⭐ Recommended | Llama 3.3 70B via Groq (free) |
| `OPENAI_API_KEY` | Optional | GPT-3.5-turbo fallback |
| `QDRANT_URL` | Optional | Remote Qdrant (default: in-memory) |
| `EMBEDDING_MODEL_PATH` | Optional | Path to fine-tuned MiniLM |

---

## ML Models

| Model | Size | Purpose | Location |
|---|---|---|---|
| `all-MiniLM-L6-v2` | ~90MB | Text embeddings (ONNX) | HuggingFace (auto-downloaded) |
| `ticket-minilm-finetuned` | ~90MB | Domain fine-tuned embeddings | `backend/models/` (gitignored) |
| `distilbert-base-uncased` | ~268MB | Sequence classification base | HuggingFace (auto-downloaded) |
| `priority-distilbert` | ~268MB | Priority classifier (94% acc) | `backend/models/` (gitignored) |

> **Note**: Model files are gitignored. Run the training scripts to regenerate them locally.
> See `scripts/train_priority_classifier.py` and `scripts/finetune_embeddings.py`.
