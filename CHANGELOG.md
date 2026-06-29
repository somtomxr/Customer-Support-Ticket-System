# Changelog

All notable changes to this project will be documented in this file.

---

## [2.0.0] — 2026-06-29

### 🚀 Major Upgrade: Full ML Intelligence Stack

This release transforms the system from a basic template-based support tool into a
production-grade AI-powered ticket management platform.

---

### ✨ New Features

#### Phase 1 — RAG Pipeline (`routers/ai_suggest.py`)
- **Retrieve-then-Generate**: Before calling the LLM, the system now finds the 3 most
  similar *resolved* tickets from Qdrant and injects their resolution comments as context
- **`_build_rag_context()`**: Pulls actual agent replies from past tickets to ground the LLM
- **`method` field in response**: Returns `"rag"` | `"llm_only"` | `"template"` so callers
  know which path fired

#### Phase 2 — Qdrant Vector Database (`similarity_engine.py`)
- Replaced NumPy brute-force cosine loop with **Qdrant** in-memory vector store
- Uses `QdrantClient(":memory:")` — zero infra, instant setup
- `query_points()` API with `status=resolved` payload filtering for RAG
- Configurable via `QDRANT_URL` env var to switch to a persistent remote instance

#### Phase 3 — LangChain + Groq LLM (`routers/ai_suggest.py`)
- Replaced raw `httpx.post` to OpenAI with **LangChain Expression Language (LCEL)** chain:
  `ChatPromptTemplate | ChatGroq | StrOutputParser`
- **Primary LLM**: Groq — Llama 3.3 70B (free, 14,400 req/day, no credit card)
- **Fallback**: `ChatOpenAI` (GPT-3.5-turbo) if `OPENAI_API_KEY` is set
- **Final fallback**: Static template dict if no API key is configured

#### Phase 4 — Fine-tuned Embedding Model (`scripts/finetune_embeddings.py`)
- New script: generates similar/dissimilar ticket pairs via Groq auto-labelling
- Fine-tunes `sentence-transformers/all-MiniLM-L6-v2` on domain-specific ticket data
- Mean cosine similarity improvement: **0.41 → 0.42** on held-out pairs
- Saved to `backend/models/ticket-minilm-finetuned/`
- Activated via `EMBEDDING_MODEL_PATH` env var

#### Phase 5 — DistilBERT Priority Classifier (`scripts/train_priority_classifier.py`)
- Fine-tuned `distilbert-base-uncased` as a 3-class classifier (low / medium / urgent)
- **LLM-assisted data labelling**: Groq (Llama 3.3 70B) auto-labels tickets missing priorities
- Synthetic data generation: 950 tickets generated via Claude → imported via
  `scripts/import_synthetic_tickets.py` → total training corpus: **1,071 tickets**
- Accuracy improvement: **40% → 94%** (215-ticket validation set)
- Full classification report: precision 0.94, recall 0.94, f1 0.94 (macro avg)
- Saved to `backend/models/priority-distilbert/` — server auto-loads on startup
- Returns `priority_confidence` score (softmax probability) in API responses

---

### 🔧 Changed

| File | What changed |
|---|---|
| `backend/routers/ai_suggest.py` | Full rewrite: RAG + LangChain + Groq |
| `backend/similarity_engine.py` | NumPy → Qdrant, DistilBERT classifier support, fine-tuned model path |
| `backend/routers/similar_tickets.py` | Updated to use Qdrant `query_points()` API (v1.18+) |
| `backend/requirements.txt` | Added: `qdrant-client`, `langchain-groq`, `langchain-openai`, `langchain-core`, `sentence-transformers`, `datasets`, `accelerate`, `transformers`, `torch` |
| `backend/.env.example` | Added `GROQ_API_KEY`, `QDRANT_URL`, `EMBEDDING_MODEL_PATH` |

---

### ➕ New Files

| File | Purpose |
|---|---|
| `backend/scripts/finetune_embeddings.py` | Fine-tune MiniLM on ticket data (Phase 4) |
| `backend/scripts/train_priority_classifier.py` | Train DistilBERT priority classifier (Phase 5) |
| `backend/scripts/import_synthetic_tickets.py` | Import Claude-generated synthetic tickets to DB |
| `CHANGELOG.md` | This file |
| `ARCHITECTURE.md` | System architecture diagram and component breakdown |

---

### 🗑️ Removed / Replaced

- Raw `httpx.post` to OpenAI GPT-3.5-turbo → replaced with LangChain + Groq
- NumPy in-memory similarity search → replaced with Qdrant vector store
- Static `REPLY_TEMPLATES` dict as primary suggestion → demoted to last fallback only

---

### ⚙️ Breaking Changes (for deployers)

- **`OPENAI_API_KEY` is no longer required** — add `GROQ_API_KEY` instead (free)
- Server startup now requires Qdrant client to initialise — add `qdrant-client` to env
- `backend/models/` directory is created at runtime — do **not** commit it (gitignored)

---

### 📊 Numbers

| Metric | Before (v1.0) | After (v2.0) |
|---|---|---|
| Tickets in DB | 121 | 1,071 |
| Priority classifier accuracy | 40% (k-NN) | **94% (DistilBERT)** |
| AI reply method | Template dict | RAG + Llama 3.3 70B |
| Vector search | NumPy O(n) loop | Qdrant HNSW index |
| LLM cost | Paid (OpenAI) | **Free (Groq)** |
| New scripts | 0 | 3 |
| New dependencies | 0 | 9 |

---

## [1.0.0] — 2026-06-16

### Initial Release
- FastAPI backend with JWT auth, CRUD tickets, comments, categories
- React frontend with role-based dashboards (Customer / Agent)
- SQLite database with seeded sample data (121 tickets)
- Semantic similar ticket search (fastembed MiniLM + NumPy cosine)
- Weighted k-NN priority prediction
- Template-based AI reply suggestions (optional OpenAI integration)
- Deployed on Render (backend) + Vercel (frontend)
