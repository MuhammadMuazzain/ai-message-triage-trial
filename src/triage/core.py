# =============================================================================
# CHANGES ADDED TO THIS FILE (relative to original client baseline):
#
# 1. New dataclass: Extraction (sender_type, urgency, requested_action,
#    unit_mention, callback_number, property_name) - all six fields from
#    Isaac's extraction spec, attached to every triage result.
#
# 2. TriageResult gains an `extraction` field (Extraction, default_factory).
#
# 3. triage_message(): debug log at entry, info logs before every routed
#    return (human_review, skip, auto_draft).
#
# 4. New private helpers: _extract(), _detect_sender_type(),
#    _detect_urgency(), _detect_requested_action(), _extract_unit_mention().
#    _extract() wraps _extract_unit_mention in try/except with warning log.
#
# 5. _detect_urgency() checks both subject and body (subject-only urgency fix).
#
# 6. _extract_unit_mention() regex tightened so only the street name or unit
#    code is returned, never surrounding prose words.
#
# 7. triage_message() edge-case guards added:
#    - Non-dict input returns human_review with warning (invalid_message_type).
#    - subject/body/sender are .strip()ed so whitespace-only strings normalise
#      to "" and never accidentally match routing or extraction terms.
# =============================================================================

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


# --- NEW: structured extraction dataclass added for improvement deliverable ---
@dataclass
class Extraction:
    sender_type: str
    urgency: str
    requested_action: str
    unit_mention: str | None
    # callback_number and property_name complete Isaac's full extraction spec
    callback_number: str | None
    property_name: str | None
# --- END NEW ---


@dataclass
class TriageResult:
    route: str
    category: str
    confidence: float
    reason: str
    draft: Draft | None = None
    warnings: list[str] = field(default_factory=list)
    # --- NEW: extraction field added; default_factory keeps existing tests passing ---
    extraction: Extraction = field(
        default_factory=lambda: Extraction(
            sender_type="unknown",
            urgency="low",
            requested_action="general property management inquiry",
            unit_mention=None,
            callback_number=None,
            property_name=None,
        )
    )
    # --- END NEW ---


SYSTEM_SUBJECTS = ("weekly activity summary", "daily report", "system generated")

LEGAL_TERMS = ("attorney", "lawsuit", "sue", "court", "legal action")
FAIR_HOUSING_TERMS = ("section 8", "voucher", "housing voucher", "emotional support animal", "service animal")
MAINTENANCE_TERMS = ("leak", "mold", "no heat", "no hot water", "flood", "electrical", "sparks")
MONEY_TERMS = ("invoice", "payment", "refund", "deposit", "wire", "bank")

# --- NEW: urgency and keyword constants for extraction helpers ---
_URGENCY_HIGH = (
    "today", "now", "getting worse", "no heat", "no hot water",
    "flood", "flooding", "emergency", "immediately", "urgent",
)
_URGENCY_MEDIUM_TERMS = LEGAL_TERMS + MONEY_TERMS + (
    "complaint", "dispute", "unhappy", "unacceptable",
)

_TOUR_KEYWORDS = ("tour", "showing", "available", "availability", "visit")
_APPLICATION_KEYWORDS = ("application", "applied", "submitted", "apply")
_AMENITY_KEYWORDS = ("parking", "laundry", "amenity", "amenities", "gym", "pool", "storage")
_LEASE_KEYWORDS = ("lease", "renewal", "renew", "lease term", "move-in", "move in", "move out")
# --- END NEW ---


def triage_message(message: dict[str, Any]) -> TriageResult:
    """Classify one inbound message and optionally create a simple draft."""
    # --- NEW: guard against None or non-dict input - fail closed to human_review ---
    if not isinstance(message, dict):
        logger.warning("invalid_message_type", extra={"type": type(message).__name__})
        return TriageResult(
            route="human_review",
            category="invalid_input",
            confidence=0.95,
            reason="Message is not a valid dictionary.",
            warnings=["invalid_message_type"],
        )
    # --- END NEW ---

    # --- NEW: .strip() normalises whitespace-only strings to "" before any matching ---
    subject = str(message.get("subject") or "").strip()
    body    = str(message.get("body")    or "").strip()
    sender  = str(message.get("sender") or "").strip()
    # --- END NEW ---
    text = f"{subject}\n{body}".lower()

    # --- NEW: debug log at entry so every processed message is traceable ---
    logger.debug("triage_start", extra={"message_id": message.get("id"), "sender": sender})
    # --- END NEW ---

    if not sender or "@" not in sender:
        logger.warning("invalid_sender", extra={"message_id": message.get("id")})
        # --- NEW: info log before human_review return ---
        logger.info("routed_to_human_review", extra={"message_id": message.get("id"), "category": "invalid_input", "reason": "Sender is missing or invalid."})
        # --- END NEW ---
        return TriageResult(
            route="human_review",
            category="invalid_input",
            confidence=0.95,
            reason="Sender is missing or invalid.",
            warnings=["invalid_sender"],
            extraction=_extract(subject, body, sender, "invalid_input"),
        )

    if any(term in subject.lower() for term in SYSTEM_SUBJECTS):
        # --- NEW: info log before skip return (was missing) ---
        logger.info("routed_to_skip", extra={"message_id": message.get("id")})
        # --- END NEW ---
        return TriageResult(
            route="skip",
            category="system",
            confidence=0.9,
            reason="System notification does not need a response.",
            extraction=_extract(subject, body, sender, "system"),
        )

    if _contains_any(text, LEGAL_TERMS):
        # --- NEW: info log before human_review return ---
        logger.info("routed_to_human_review", extra={"message_id": message.get("id"), "category": "legal", "reason": "Potential legal escalation."})
        # --- END NEW ---
        return TriageResult(
            route="human_review",
            category="legal",
            confidence=0.75,
            reason="Potential legal escalation.",
            warnings=["legal_review_required"],
            extraction=_extract(subject, body, sender, "legal"),
        )

    if _contains_any(text, FAIR_HOUSING_TERMS):
        # --- NEW: info log before human_review return ---
        logger.info("routed_to_human_review", extra={"message_id": message.get("id"), "category": "fair_housing", "reason": "Sensitive housing/accommodation topic."})
        # --- END NEW ---
        return TriageResult(
            route="human_review",
            category="fair_housing",
            confidence=0.7,
            reason="Sensitive housing/accommodation topic.",
            warnings=["policy_review_required"],
            extraction=_extract(subject, body, sender, "fair_housing"),
        )

    if _contains_any(text, MAINTENANCE_TERMS):
        # --- NEW: info log before human_review return ---
        logger.info("routed_to_human_review", extra={"message_id": message.get("id"), "category": "maintenance", "reason": "Possible maintenance issue."})
        # --- END NEW ---
        return TriageResult(
            route="human_review",
            category="maintenance",
            confidence=0.65,
            reason="Possible maintenance issue.",
            warnings=["maintenance_review_required"],
            extraction=_extract(subject, body, sender, "maintenance"),
        )

    if _contains_any(text, MONEY_TERMS):
        # --- NEW: info log before human_review return ---
        logger.info("routed_to_human_review", extra={"message_id": message.get("id"), "category": "money", "reason": "Money/payment related message."})
        # --- END NEW ---
        return TriageResult(
            route="human_review",
            category="money",
            confidence=0.65,
            reason="Money/payment related message.",
            warnings=["payment_review_required"],
            extraction=_extract(subject, body, sender, "money"),
        )

    # --- NEW: info log before auto_draft return ---
    logger.info("routed_to_auto_draft", extra={"message_id": message.get("id")})
    # --- END NEW ---
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
        extraction=_extract(subject, body, sender, "leasing_general"),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# --- NEW: _extract() and all helpers below are new; none existed in baseline ---

def _extract(subject: str, body: str, sender: str, category: str) -> Extraction:
    try:
        unit_mention = _extract_unit_mention(subject, body)
    except Exception as e:
        # Regex failure must never crash a triage run; log and return None safely
        logger.warning("unit_mention_extract_failed", extra={"message_id": "unknown", "error": str(e)})
        unit_mention = None
    return Extraction(
        sender_type=_detect_sender_type(sender),
        urgency=_detect_urgency(body, subject),
        requested_action=_detect_requested_action(subject, body, category),
        unit_mention=unit_mention,
        callback_number=_extract_callback_number(subject, body),
        property_name=_extract_property_name(subject, body),
    )


def _detect_sender_type(sender: str) -> str:
    local = sender.split("@")[0].lower() if "@" in sender else sender.lower()
    if "tenant" in local:
        return "tenant"
    if "prospect" in local:
        return "prospect"
    if "vendor" in local:
        return "vendor"
    if "noreply" in local:
        return "system"
    return "unknown"


def _detect_urgency(body: str, subject: str = "") -> str:
    # Subject is included so that "No heat" in the subject line alone triggers high urgency
    text = f"{subject}\n{body}".lower()
    if any(re.search(rf"\b{re.escape(t)}\b", text) for t in _URGENCY_HIGH):
        return "high"
    if any(re.search(rf"\b{re.escape(t)}\b", text) for t in _URGENCY_MEDIUM_TERMS):
        return "medium"
    return "low"


def _detect_requested_action(subject: str, body: str, category: str) -> str:
    text = f"{subject}\n{body}".lower()

    if category == "maintenance":
        return "request maintenance visit or repair"
    if category == "legal":
        return "escalate legal dispute or court matter"
    if category == "fair_housing":
        return "ask fair housing policy or accommodation"
    if category == "money":
        return "ask billing payment invoice refund or deposit"
    if category == "system":
        return "review automated leasing or system summary"

    if category == "leasing_general":
        if any(kw in text for kw in _TOUR_KEYWORDS):
            return "schedule apartment tour or check availability"
        if any(kw in text for kw in _APPLICATION_KEYWORDS):
            return "acknowledge application submitted wait next steps"
        if any(kw in text for kw in _AMENITY_KEYWORDS):
            return "ask building amenities parking or services"
        if any(kw in text for kw in _LEASE_KEYWORDS):
            return "ask about lease term renewal or dates"

    return "general property management inquiry"


def _extract_callback_number(subject: str, body: str) -> str | None:
    """Extract a phone number from subject or body if one is present.

    Matches common US formats: (555) 123-4567, 555-123-4567, 555.123.4567,
    +1 555 123 4567, and plain 10-digit runs. Returns the first match or None.
    """
    text = f"{subject} {body}"
    pattern = re.compile(
        r"(?:\+1[\s\-.]?)?"           # optional country code
        r"(?:\(?\d{3}\)?[\s\-.]?)"    # area code
        r"\d{3}[\s\-.]?\d{4}"         # local number
    )
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def _extract_property_name(subject: str, body: str) -> str | None:
    """Extract a property or building name if explicitly mentioned.

    Looks for patterns like "123 Maple Street Apartments", "The Oaks",
    "Riverside Condos", or any Title-Case noun phrase followed by a
    property-type word. Returns None if nothing found.
    """
    text = f"{subject} {body}"
    pattern = re.compile(
        r"\b(?:The\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*"
        r"\s+(?:Apartments?|Condos?|Complex|Residences?|Towers?|Plaza|"
        r"Properties|Building|Community|Estate|Manor|Park|Village)\b"
    )
    match = pattern.search(text)
    return match.group(0).strip() if match else None


def _extract_unit_mention(subject: str, body: str) -> str | None:
    text = f"{subject} {body}"

    # Unit/apt keyword + digit code - case-insensitive so "unit 4b" and "Unit 4B" both work
    unit_pattern = re.compile(r"\b(?:unit|apt|suite|ste|#)\s*\d[\dA-Za-z\-]*", re.IGNORECASE)
    match = unit_pattern.search(text)
    if match:
        return match.group(0).strip()

    # Proper house-number address: digit immediately before a Title-Case street name.
    # Case-sensitive [A-Z] prevents prose words like "bedroom" from matching as street names.
    numbered_pattern = re.compile(
        r"\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*"
        r"\s+(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court)\b"
    )
    match = numbered_pattern.search(text)
    if match:
        return match.group(0).strip()

    # Named street without a leading number: "Maple Street", "Oak Avenue".
    # Case-sensitive so only Title-Case words are accepted as street names.
    named_pattern = re.compile(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*"
        r"\s+(?:Street|Avenue|Road|Boulevard|Drive|Lane|Court)\b"
    )
    match = named_pattern.search(text)
    if match:
        return match.group(0).strip()

    return None

# --- END NEW ---


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _reply_subject(subject: str) -> str:
    subject = subject.strip() or "Your message"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"
