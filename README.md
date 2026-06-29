# Semantic Ticket Retrieval & Priority Prediction System

A production-grade, full-stack AI-powered customer support ticketing platform featuring
semantic retrieval, RAG-based reply generation, and a fine-tuned DistilBERT priority
classifier — all running locally for free.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi)
![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant-red?logo=qdrant)
![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?logo=langchain)
![Groq](https://img.shields.io/badge/LLM-Groq_Llama_3.3_70B-orange)
![HuggingFace](https://img.shields.io/badge/🤗_HuggingFace-DistilBERT-yellow)
![SQLite](https://img.shields.io/badge/Database-SQLite-4169E1?logo=sqlite)

---

## Features

| Feature | Description |
|---|---|
| **Role-Based Access** | Customer and Agent dashboards with distinct capabilities |
| **Ticket Lifecycle** | Open → In Progress → Resolved with status transition validation |
| **JWT Authentication** | Secure login with bcrypt password hashing |
| **REST API** | Full CRUD with Swagger docs at `/docs` |
| **🔍 Semantic Search** | Qdrant vector DB + fine-tuned MiniLM finds tickets by *meaning*, not keywords |
| **🤖 RAG Reply Suggestions** | Retrieves resolved similar tickets → feeds to Llama 3.3 70B → generates contextual reply |
| **🧠 Priority Classifier** | DistilBERT fine-tuned on 1,071 tickets — **94% accuracy** — returns softmax confidence |
| **🔗 LangChain LCEL** | `ChatPromptTemplate \| ChatGroq \| StrOutputParser` pipeline |
| **💬 LLM-Assisted Labelling** | Groq auto-labels unlabelled tickets for classifier training |
| **⚡ Free LLM** | Groq (Llama 3.3 70B) — 14,400 req/day free, no credit card |
| **Comment System** | Threaded comments with author attribution |

---

## ML Architecture

```
Ticket text
    │
    ▼ fastembed (MiniLM-L6-v2, ONNX, fine-tuned)
Embedding vector (384-dim)
    │
    ├──▶ Qdrant HNSW index ──▶ Top-5 similar tickets
    │         │
    │         └──▶ Resolved tickets ──▶ RAG context
    │                                       │
    │                              LangChain LCEL chain
    │                              ChatPromptTemplate
    │                                       │
    │                              Groq (Llama 3.3 70B)
    │                                       │
    │                              Contextual reply ◀──────────┐
    │                                                           │
    └──▶ DistilBERT classifier ──▶ Priority + confidence score─┘
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full component diagram.

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Database | SQLite (SQLAlchemy ORM) |
| Auth | JWT + bcrypt |
| Embeddings | fastembed (MiniLM-L6-v2, ONNX — no GPU required) |
| Vector DB | Qdrant (in-memory, upgradeable to remote) |
| LLM Chain | LangChain LCEL (`langchain-groq` + `langchain-openai`) |
| Primary LLM | Groq — Llama 3.3 70B (free) |
| Priority Model | DistilBERT (HuggingFace Transformers, Trainer API) |
| ML Training | sentence-transformers, HuggingFace datasets, accelerate |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + Vite |
| Routing | React Router |
| HTTP | Axios |
| Styling | CSS Modules |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- A free [Groq API key](https://console.groq.com) (takes 2 minutes)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your GROQ_API_KEY=gsk_...

python seed.py                    # seed initial data
uvicorn main:app --reload
```

API available at: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

App available at: `http://localhost:5173`

---

## Demo Credentials

| Role | Email | Password |
|---|---|---|
| Agent | `agent@support.com` | `password123` |
| Customer | `customer@example.com` | `password123` |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | JWT login |
| GET | `/api/tickets` | List tickets (filtered) |
| POST | `/api/tickets` | Create ticket |
| PATCH | `/api/tickets/{id}` | Update ticket |
| GET | `/api/similar-tickets/{id}` | Semantic similar + priority prediction |
| POST | `/api/ai/suggest-reply/{id}` | RAG reply suggestion (Groq) |
| GET | `/api/categories` | List categories |
| GET | `/api/comments/{ticket_id}` | Ticket comments |
| POST | `/api/comments/{ticket_id}` | Add comment |
| GET | `/api/users/me` | Current user profile |
| GET | `/api/stats` | Dashboard statistics |

---

## ML Training Scripts

These are one-time scripts to improve model quality. Run after the server is set up.

### Phase 4 — Fine-tune Embedding Model
```bash
cd backend
source venv/bin/activate
python scripts/finetune_embeddings.py
# Saves to: backend/models/ticket-minilm-finetuned/
# Then add to .env: EMBEDDING_MODEL_PATH=./models/ticket-minilm-finetuned
```

### Phase 5 — Train Priority Classifier
```bash
cd backend
source venv/bin/activate
python scripts/train_priority_classifier.py
# Saves to: backend/models/priority-distilbert/
# Server auto-detects on next restart — no config needed
```

**Results with 1,071 training tickets:**

```
              precision    recall  f1-score   support
         low       0.95      0.99      0.97        70
      medium       0.91      0.92      0.92        79
      urgent       0.97      0.91      0.94        66
    accuracy                           0.94       215
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | SQLite: `sqlite:///./support_tickets.db` |
| `SECRET_KEY` | ✅ | — | JWT signing secret |
| `ALGORITHM` | ✅ | `HS256` | JWT algorithm |
| `FRONTEND_URL` | ✅ | `http://localhost:5173` | CORS origin |
| `GROQ_API_KEY` | ⭐ | — | Free at console.groq.com |
| `OPENAI_API_KEY` | Optional | — | Fallback if Groq unavailable |
| `QDRANT_URL` | Optional | in-memory | Remote Qdrant URL |
| `EMBEDDING_MODEL_PATH` | Optional | MiniLM default | Path to fine-tuned embeddings |

---

## Project Structure

```
customer-support-ticket-system/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── similarity_engine.py       # Qdrant + embeddings + DistilBERT
│   ├── models.py                  # SQLAlchemy models
│   ├── schemas.py                 # Pydantic schemas
│   ├── auth.py                    # JWT authentication
│   ├── database.py                # DB session setup
│   ├── routers/
│   │   ├── ai_suggest.py          # RAG + LangChain + Groq
│   │   ├── similar_tickets.py     # Semantic search endpoint
│   │   ├── tickets.py             # Ticket CRUD
│   │   ├── comments.py            # Comments
│   │   ├── auth_routes.py         # Login/register
│   │   ├── categories.py          # Categories
│   │   └── users.py               # User profile
│   ├── scripts/
│   │   ├── finetune_embeddings.py       # Phase 4: fine-tune MiniLM
│   │   ├── train_priority_classifier.py  # Phase 5: train DistilBERT
│   │   └── import_synthetic_tickets.py  # Import generated ticket data
│   ├── seed.py                    # Initial data seeder
│   ├── rich_seed.py               # Extended seeder (121 tickets)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/
│       ├── components/
│       └── ...
├── ARCHITECTURE.md                # System architecture + diagrams
├── CHANGELOG.md                   # Version history
├── README.md                      # This file
├── render.yaml                    # Render deployment config
└── vercel.json                    # Vercel frontend config
```

---

## What's New in v2.0

| | v1.0 | v2.0 |
|---|---|---|
| Vector search | NumPy O(n) loop | Qdrant HNSW index |
| AI replies | Static template dict | RAG + Llama 3.3 70B |
| Priority | k-NN vote | DistilBERT (**94% accuracy**) |
| LLM cost | Paid (OpenAI) | **Free (Groq)** |
| Tickets in DB | 121 | 1,071 |
| LLM framework | Raw httpx | LangChain LCEL |

See [CHANGELOG.md](./CHANGELOG.md) for the full diff.

---

## License

MIT
