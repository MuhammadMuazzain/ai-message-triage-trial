from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Draft:
    subject: str
    body: str


@dataclass
class TriageResult:
    route: str
    category: str
    confidence: float
    reason: str
    draft: Draft | None = None
    warnings: list[str] = field(default_factory=list)


SYSTEM_SUBJECTS = ("weekly activity summary", "daily report", "system generated")

LEGAL_TERMS = ("attorney", "lawsuit", "sue", "court", "legal action")
FAIR_HOUSING_TERMS = ("section 8", "voucher", "housing voucher", "emotional support animal", "service animal")
MAINTENANCE_TERMS = ("leak", "mold", "no heat", "no hot water", "flood", "electrical", "sparks")
MONEY_TERMS = ("invoice", "payment", "refund", "deposit", "wire", "bank")


def triage_message(message: dict[str, Any]) -> TriageResult:
    """Classify one inbound message and optionally create a simple draft.

    This is intentionally basic. Candidates should improve this function or
    add a small supporting layer without replacing the whole project.
    """
    subject = str(message.get("subject") or "")
    body = str(message.get("body") or "")
    sender = str(message.get("sender") or "")
    text = f"{subject}\n{body}".lower()

    if not sender or "@" not in sender:
        logger.warning("invalid_sender", extra={"message_id": message.get("id")})
        return TriageResult(
            route="human_review",
            category="invalid_input",
            confidence=0.95,
            reason="Sender is missing or invalid.",
            warnings=["invalid_sender"],
        )

    if any(term in subject.lower() for term in SYSTEM_SUBJECTS):
        return TriageResult(
            route="skip",
            category="system",
            confidence=0.9,
            reason="System notification does not need a response.",
        )

    if _contains_any(text, LEGAL_TERMS):
        return TriageResult(
            route="human_review",
            category="legal",
            confidence=0.75,
            reason="Potential legal escalation.",
            warnings=["legal_review_required"],
        )

    if _contains_any(text, FAIR_HOUSING_TERMS):
        return TriageResult(
            route="human_review",
            category="fair_housing",
            confidence=0.7,
            reason="Sensitive housing/accommodation topic.",
            warnings=["policy_review_required"],
        )

    if _contains_any(text, MAINTENANCE_TERMS):
        return TriageResult(
            route="human_review",
            category="maintenance",
            confidence=0.65,
            reason="Possible maintenance issue.",
            warnings=["maintenance_review_required"],
        )

    if _contains_any(text, MONEY_TERMS):
        return TriageResult(
            route="human_review",
            category="money",
            confidence=0.65,
            reason="Money/payment related message.",
            warnings=["payment_review_required"],
        )

    return TriageResult(
        route="auto_draft",
        category="leasing_general",
        confidence=0.55,
        reason="General leasing message with no sensitive terms.",
        draft=Draft(
            subject=_reply_subject(subject),
            body=(
                "Hi, thanks for reaching out. We received your message and "
                "will follow up with the next step shortly."
            ),
        ),
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _reply_subject(subject: str) -> str:
    subject = subject.strip() or "Your message"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"
