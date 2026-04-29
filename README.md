# Customer Support Ticket System

A full-stack customer support ticketing platform with role-based access control, ticket lifecycle management, and AI-assisted reply suggestions.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/Database-SQLite%20%7C%20PostgreSQL-4169E1?logo=postgresql)

## Features

- **Role-Based Access Control**: Customer and Agent dashboards with distinct capabilities
- **Ticket Lifecycle**: Open → In Progress → Resolved with status transition validation
- **JWT Authentication**: Secure login with bcrypt password hashing
- **12+ RESTful API Endpoints**: Complete CRUD operations with Swagger docs
- **AI Reply Suggestions**: Template-based + optional OpenAI-powered agent replies
- **Real-time Search & Filtering**: Filter tickets by status, priority, category
- **Comment System**: Threaded comments on tickets with author attribution
- **Responsive UI**: Clean, modern React SPA with Tailwind CSS

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, React Router, Axios |
| Backend | Python, FastAPI, SQLAlchemy ORM, Pydantic |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Deployment | Vercel (frontend), Render (backend) |

## Project Structure

```
customer-support-ticket-system/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # Database connection & session
│   ├── models.py            # SQLAlchemy models (User, Ticket, Comment, Category)
│   ├── schemas.py           # Pydantic validation schemas
│   ├── auth.py              # JWT authentication utilities
│   ├── seed.py              # Database seed script
│   ├── requirements.txt
│   ├── .env.example
│   └── routers/
│       ├── auth_routes.py   # Register, login, profile
│       ├── tickets.py       # Ticket CRUD + status management
│       ├── comments.py      # Comment system
│       ├── categories.py    # Category management
│       ├── users.py         # Agent listing
│       └── ai_suggest.py    # AI reply suggestion engine
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Root component + routing
│   │   ├── main.jsx         # Entry point
│   │   ├── context/         # React Context (AuthContext)
│   │   ├── services/        # API client (Axios)
│   │   ├── components/      # Reusable components
│   │   └── pages/           # Page components
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
└── README.md
```

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm or yarn

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Seed database with demo data
python seed.py

# Start the server
uvicorn main:app --reload --port 8000
```

API documentation available at: http://localhost:8000/docs

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend available at: http://localhost:5173

### Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Customer | rahul@example.com | password123 |
| Customer | priya@example.com | password123 |
| Agent | som@support.com | password123 |
| Agent | neha@support.com | password123 |

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/auth/register` | Register new user | No |
| POST | `/api/auth/login` | Login & get JWT token | No |
| GET | `/api/auth/me` | Get current user profile | Yes |
| GET | `/api/tickets/` | List tickets (filtered) | Yes |
| POST | `/api/tickets/` | Create new ticket | Yes |
| GET | `/api/tickets/{id}` | Get ticket details | Yes |
| PUT | `/api/tickets/{id}` | Update ticket | Yes |
| PATCH | `/api/tickets/{id}/status` | Change ticket status | Yes |
| PATCH | `/api/tickets/{id}/assign` | Assign ticket to agent | Agent |
| GET | `/api/tickets/stats` | Dashboard statistics | Yes |
| GET | `/api/tickets/{id}/comments` | List ticket comments | Yes |
| POST | `/api/tickets/{id}/comments` | Add comment | Yes |
| GET | `/api/categories/` | List categories | No |
| POST | `/api/categories/` | Create category | Agent |
| GET | `/api/users/agents` | List agents | Yes |
| POST | `/api/ai/suggest-reply` | Get AI reply suggestion | Agent |

## Deployment

### Frontend → Vercel
1. Push to GitHub
2. Import project in Vercel
3. Set build command: `npm run build`
4. Set output directory: `dist`
5. Add environment variable: `VITE_API_URL=https://your-backend.onrender.com`

### Backend → Render
1. Push to GitHub
2. Create new Web Service on Render
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env.example`

## Database Schema

```
users           tickets              comments         categories
─────────       ──────────           ──────────       ──────────
id (PK)         id (PK)              id (PK)          id (PK)
name            title                content          name
email (UQ)      description          ticket_id (FK)   description
password_hash   status               user_id (FK)
role            priority             is_ai_generated
is_active       customer_id (FK)     created_at
created_at      agent_id (FK)
                category_id (FK)
                created_at
                updated_at
```

## License

MIT
