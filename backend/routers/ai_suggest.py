import os
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import User, Ticket, Comment
from schemas import AISuggestRequest, AISuggestResponse
from auth import get_current_user, require_role
import similarity_engine

router = APIRouter(prefix="/api/ai", tags=["AI Suggestions"])

# Template-based responses organized by category and sentiment
REPLY_TEMPLATES = {
    "billing": [
        "Thank you for reaching out about your billing concern. I've reviewed your account and I can see the issue. Let me process the necessary adjustment. You should see the changes reflected within 2-3 business days. Is there anything else I can help with?",
        "I understand billing issues can be frustrating. I've looked into this and found the discrepancy. I'm initiating a correction on our end. You'll receive a confirmation email once it's processed. Please don't hesitate to reach out if you need further assistance.",
        "Thank you for bringing this to our attention. After reviewing your billing history, I can confirm the error. I've submitted a request to our billing team to resolve this promptly. You should receive an updated invoice within 48 hours.",
    ],
    "technical": [
        "Thank you for reporting this technical issue. Based on your description, this appears to be related to a known configuration issue. Could you try the following steps: 1) Clear your browser cache, 2) Disable any browser extensions, 3) Try accessing from an incognito window. If the issue persists, please share any error messages you see.",
        "I've reviewed the technical details you provided. This seems to be a compatibility issue. I'd recommend updating to the latest version of the application. If that doesn't resolve it, I'll escalate this to our engineering team with your details for a deeper investigation.",
        "Thank you for the detailed report. I've been able to reproduce the issue on our end and have logged it as a bug. Our development team will prioritize this fix. In the meantime, here's a workaround you can try to continue your work without interruption.",
    ],
    "account": [
        "I understand you're having trouble with your account. For security purposes, I need to verify your identity. Could you please confirm the email address associated with your account? Once verified, I'll be able to assist you with the necessary changes.",
        "Thank you for contacting us about your account. I've reviewed your account details and can help resolve this. I've made the necessary updates on our end. Please try logging out and back in to see the changes. Let me know if everything looks correct.",
        "I see the issue with your account settings. I've gone ahead and made the adjustment. For future reference, you can manage these settings from your profile page under Settings > Account Preferences. Is there anything else I can help with?",
    ],
    "general": [
        "Thank you for contacting our support team. I've carefully reviewed your request and I'm happy to help. Let me look into this further and get back to you with a detailed solution. In the meantime, is there any additional information you can provide that might help?",
        "I appreciate you reaching out to us. I understand your concern and want to make sure we resolve this properly. I've documented your issue and will work on finding the best solution. You should hear back from us within 24 hours with an update.",
        "Thank you for your patience. I've looked into your request and have a solution ready. Please follow the steps I've outlined below, and don't hesitate to reach out again if you need any clarification or further assistance. We value your feedback!",
    ],
}

# LLM model config
# Priority: GROQ_API_KEY → OPENAI_API_KEY → template fallback
GROQ_MODEL   = "llama-3.3-70b-versatile"   # free, high quality
OPENAI_MODEL = "gpt-3.5-turbo"              # fallback if OpenAI key provided


def _get_template_suggestion(ticket: Ticket) -> str:
    """Generate a reply suggestion using templates based on ticket context."""
    category_name = ticket.category.name.lower() if ticket.category else "general"
    template_key = "general"
    for key in REPLY_TEMPLATES:
        if key in category_name:
            template_key = key
            break
    return random.choice(REPLY_TEMPLATES[template_key])


def _build_rag_context(ticket: Ticket, db: Session) -> str:
    """
    Phase 1: Retrieve top-3 semantically similar *resolved* tickets and
    extract their last comment to build a RAG context block.
    Returns an empty string when no resolved neighbours are found.
    """
    if not similarity_engine.is_available():
        return ""

    all_tickets = db.query(Ticket).all()
    similar = similarity_engine.find_similar(
        query_ticket=ticket, all_tickets=all_tickets, db=db, top_k=3,
    )

    resolved_matches = [(t, s) for t, s in similar if t.status == "resolved"]
    if not resolved_matches:
        return ""

    context_parts: list[str] = []
    for past_ticket, _score in resolved_matches:
        last_comment = (
            db.query(Comment)
            .filter(Comment.ticket_id == past_ticket.id)
            .order_by(Comment.created_at.desc())
            .first()
        )
        resolution_text = last_comment.content if last_comment else "(no comment recorded)"
        context_parts.append(
            f"Past resolution: {past_ticket.title} — {past_ticket.description} "
            f"— Resolution: {resolution_text}"
        )
    return "\n\n".join(context_parts)


def _build_llm_chain(groq_key: str, openai_key: str):
    """
    Return a (llm, provider_name) tuple.
    Priority: Groq (free) → OpenAI → None
    """
    if groq_key:
        from langchain_groq import ChatGroq
        return ChatGroq(model=GROQ_MODEL, api_key=groq_key, max_tokens=300), "groq"
    if openai_key:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=OPENAI_MODEL, api_key=openai_key, max_tokens=300, temperature=0.7), "openai"
    return None, None


@router.post("/suggest-reply", response_model=AISuggestResponse)
def suggest_reply(
    payload: AISuggestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["agent"])),
):
    """
    Generate an AI-assisted reply suggestion for a ticket.

    LLM priority:
      1. Groq   (GROQ_API_KEY)   — free, fast, Llama 3.3 70B
      2. OpenAI (OPENAI_API_KEY) — fallback if Groq key not set
      3. Template                — no LLM key configured, or LLM call fails

    method field in response:
      "rag"      — LLM call enriched with resolved-ticket context (RAG)
      "llm_only" — LLM call with no resolved neighbours found
      "template" — hardcoded template fallback
    """
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.category), joinedload(Ticket.comments))
        .filter(Ticket.id == payload.ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    groq_key   = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    llm, provider = _build_llm_chain(groq_key, openai_key)

    if llm is not None:
        # ── Phase 1: RAG context from resolved similar tickets ────────────────
        rag_context = _build_rag_context(ticket, db)

        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser

            comments_text = "\n".join([f"- {c.content}" for c in ticket.comments[-5:]])

            if rag_context:
                system_msg = (
                    "You are a helpful customer support agent. "
                    "Use the following past resolutions as reference when drafting your reply:\n\n"
                    "{rag_context}\n\n"
                    "Now generate a professional, empathetic reply for the current ticket."
                )
            else:
                system_msg = (
                    "You are a helpful customer support agent. "
                    "Generate a professional, empathetic reply for this support ticket."
                )

            human_msg = (
                "Ticket Title: {title}\n"
                "Ticket Description: {description}\n"
                "Category: {category}\n"
                "Priority: {priority}\n"
                "Recent Comments:\n{comments}\n\n"
                "Generate a helpful reply (2-3 paragraphs):"
            )

            # ── Phase 3: LangChain chain ──────────────────────────────────────
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_msg),
                ("human", human_msg),
            ])
            chain = prompt | llm | StrOutputParser()

            suggestion = chain.invoke({
                "rag_context": rag_context,
                "title": ticket.title,
                "description": ticket.description,
                "category": ticket.category.name if ticket.category else "General",
                "priority": ticket.priority,
                "comments": comments_text,
            })

            method = "rag" if rag_context else "llm_only"
            return AISuggestResponse(suggestion=suggestion.strip(), method=method)

        except Exception:
            # Fall through to template on any LLM error
            pass

    # Template-based fallback (original behaviour, always works)
    suggestion = _get_template_suggestion(ticket)
    return AISuggestResponse(suggestion=suggestion, method="template")
