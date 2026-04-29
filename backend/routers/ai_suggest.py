import os
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import User, Ticket, Comment
from schemas import AISuggestRequest, AISuggestResponse
from auth import get_current_user, require_role

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


def _get_template_suggestion(ticket: Ticket) -> str:
    """Generate a reply suggestion using templates based on ticket context."""
    category_name = ticket.category.name.lower() if ticket.category else "general"

    # Map category to template group
    template_key = "general"
    for key in REPLY_TEMPLATES:
        if key in category_name:
            template_key = key
            break

    templates = REPLY_TEMPLATES[template_key]
    return random.choice(templates)


@router.post("/suggest-reply", response_model=AISuggestResponse)
def suggest_reply(
    payload: AISuggestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["agent"])),
):
    """
    Generate an AI-assisted reply suggestion for a ticket.
    Uses template-based approach by default, or OpenAI if API key is configured.
    """
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.category), joinedload(Ticket.comments))
        .filter(Ticket.id == payload.ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if openai_key:
        # Use OpenAI for smarter suggestions
        try:
            import httpx

            comments_text = "\n".join(
                [f"- {c.content}" for c in ticket.comments[-5:]]
            )
            prompt = (
                f"You are a helpful customer support agent. Generate a professional, "
                f"empathetic reply for this support ticket.\n\n"
                f"Ticket Title: {ticket.title}\n"
                f"Ticket Description: {ticket.description}\n"
                f"Category: {ticket.category.name if ticket.category else 'General'}\n"
                f"Priority: {ticket.priority}\n"
                f"Recent Comments:\n{comments_text}\n\n"
                f"Generate a helpful reply (2-3 paragraphs):"
            )

            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.7,
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
            suggestion = data["choices"][0]["message"]["content"].strip()
            return AISuggestResponse(suggestion=suggestion, method="ai")
        except Exception:
            # Fallback to templates if AI fails
            pass

    # Template-based fallback
    suggestion = _get_template_suggestion(ticket)
    return AISuggestResponse(suggestion=suggestion, method="template")
