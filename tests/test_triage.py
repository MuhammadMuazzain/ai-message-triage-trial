from triage.core import triage_message


def test_general_leasing_message_gets_draft():
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Parking",
        "body": "Is parking included with the apartment?",
    })

    assert result.route == "auto_draft"
    assert result.draft is not None
    assert result.draft.subject == "Re: Parking"


def test_legal_threat_requires_human_review():
    result = triage_message({
        "sender": "tenant@example.com",
        "subject": "Problem",
        "body": "My attorney said we should sue if this is not fixed.",
    })

    assert result.route == "human_review"
    assert result.category == "legal"
    assert "legal_review_required" in result.warnings


def test_sensitive_housing_topic_requires_human_review():
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Voucher",
        "body": "Do you accept Section 8 vouchers?",
    })

    assert result.route == "human_review"
    assert result.category == "fair_housing"


def test_system_summary_is_skipped():
    result = triage_message({
        "sender": "noreply@example.com",
        "subject": "Weekly activity summary",
        "body": "Generated report.",
    })

    assert result.route == "skip"


def test_invalid_sender_fails_closed():
    result = triage_message({
        "sender": "",
        "subject": "Question",
        "body": "Can I apply?",
    })

    assert result.route == "human_review"
    assert result.category == "invalid_input"


# ---------------------------------------------------------------------------
# Extraction tests
# ---------------------------------------------------------------------------

def test_extraction_urgency_high_active_leak():
    """Tenant reporting active leak getting worse today triggers high urgency."""
    result = triage_message({
        "sender": "tenant@example.com",
        "subject": "Leak",
        "body": "The leak is getting worse and someone must come today.",
    })
    assert result.extraction.urgency == "high"


def test_extraction_urgency_high_from_subject_only():
    """High urgency term in subject alone is enough even if body is calm.

    Catches the real case where a tenant writes 'No heat' as the subject
    but describes the situation without repeating the trigger word.
    """
    result = triage_message({
        "sender": "tenant@example.com",
        "subject": "No heat",
        "body": "The heat has been off since last night and it is very cold.",
    })
    assert result.extraction.urgency == "high"


def test_extraction_urgency_medium_money_matter():
    """Money-related message is medium urgency, not routed as low-priority."""
    result = triage_message({
        "sender": "vendor@example.com",
        "subject": "Invoice follow up",
        "body": "Following up on invoice 4021. Can you confirm payment?",
    })
    assert result.extraction.urgency == "medium"


def test_extraction_legal_combined():
    """Legal threat with immediate demand: correct route, category, and urgency together."""
    result = triage_message({
        "sender": "tenant@example.com",
        "subject": "Attorney",
        "body": "My attorney told me to put this in writing. Fix the mold immediately.",
    })
    assert result.route == "human_review"
    assert result.category == "legal"
    assert result.extraction.urgency == "high"


def test_extraction_unit_mention_street_address():
    """Named street in body is extracted and contains the street name."""
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Showing",
        "body": "Is the 2 bedroom apartment on Maple Street still available?",
    })
    assert result.extraction.unit_mention is not None
    assert "Maple" in result.extraction.unit_mention

def test_non_dict_input_fails_closed():
    """Passing a non-dict (e.g. any string) must fail closed to human_review."""
    result= triage_message("This is not a dictionary")
    assert result.route == "human_review"
    assert result.category == "invalid_input"
    assert "invalid_message_type" in result.warnings


def test_whitespace_only_sender_fails_closed():
    """A sender that is only spaces must be treated the same as empty sender."""
    result = triage_message({
        "sender": "   ",
        "subject": "Question",
        "body": "Can I apply?",
    })
    assert result.route == "human_review"
    assert result.category == "invalid_input"

def test_extraction_always_returns_extraction_object():
    """Every route must return an Extraction object, never None."""
    from triage.core import Extraction
    for msg in [
        {"sender": "tenant@example.com", "subject": "Leak", "body": "Water leak."},
        {"sender": "noreply@example.com", "subject": "Daily report", "body": "Report."},
        {"sender": "prospect@example.com", "subject": "Parking", "body": "Any parking?"},
    ]:
        result = triage_message(msg)
        assert isinstance(result.extraction, Extraction)

def test_extraction_unit_mention_absent():
    """Generic message with no address returns None, not a false positive."""
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Parking",
        "body": "Is parking included with the apartment?",
    })
    assert result.extraction.unit_mention is None


def test_extraction_populated_on_system_skip():
    """Extraction is always present even on messages routed to skip."""
    result = triage_message({
        "sender": "noreply@example.com",
        "subject": "Weekly activity summary",
        "body": "System generated report for leasing activity.",
    })
    assert result.route == "skip"
    assert result.extraction is not None
    assert result.extraction.sender_type == "system"


def test_extraction_populated_on_invalid_sender():
    """Extraction is always present even when sender validation fails."""
    result = triage_message({
        "sender": "",
        "subject": "Question",
        "body": "Can I apply for the unit?",
    })
    assert result.route == "human_review"
    assert result.extraction is not None


# ---------------------------------------------------------------------------
# Routing order and reply formatting tests
# ---------------------------------------------------------------------------

def test_maintenance_check_fires_before_money_check():
    """When a message contains both a maintenance term and a money term,
    maintenance wins because it appears earlier in the routing chain.

    This matters operationally: a leak complaint that also mentions a deposit
    must go to maintenance review, not be silently downgraded to a billing
    matter.
    """
    result = triage_message({
        "sender": "tenant@example.com",
        "subject": "Leak and deposit",
        "body": "There is a leak in my kitchen. Also, when will my deposit refund be processed?",
    })
    assert result.route == "human_review"
    assert result.category == "maintenance"


def test_reply_subject_does_not_double_prefix():
    """Auto-draft reply subject must not add 'Re:' if the subject already starts with it.

    Without this guard, a message with subject 'Re: Parking' would produce a
    draft subject of 'Re: Re: Parking', which looks unprofessional and confuses
    email threading.
    """
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Re: Parking",
        "body": "Thanks for confirming. Is covered parking available?",
    })
    assert result.route == "auto_draft"
    assert result.draft is not None
    assert result.draft.subject == "Re: Parking"
    assert not result.draft.subject.lower().startswith("re: re:")


def test_extraction_unit_mention_explicit_unit_code():
    """Unit code like 'Unit 4B' in the body is extracted as-is, not the surrounding words.

    Property managers need the exact unit reference to look up records quickly.
    Returning extra context words forces manual parsing downstream.
    """
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Availability",
        "body": "I am interested in Unit 4B. Is it still available?",
    })
    assert result.extraction.unit_mention is not None
    assert result.extraction.unit_mention.lower().startswith("unit")
    assert "4B" in result.extraction.unit_mention or "4b" in result.extraction.unit_mention.lower()


def test_extraction_sender_type_unknown_for_generic_domain():
    """A sender whose local part contains none of the known keywords is 'unknown'.

    Not all senders are tenants, prospects, or vendors. Reporting 'unknown'
    rather than guessing wrong prevents incorrect workflow routing based on
    sender classification.
    """
    result = triage_message({
        "sender": "info@propertyco.com",
        "subject": "General inquiry",
        "body": "Hi, I have a question about the application process.",
    })
    assert result.extraction.sender_type == "unknown"


def test_auto_draft_body_never_fabricates_facts():
    """Auto-draft body must be a safe generic acknowledgement that makes no
    specific claims about availability, pricing, or timelines.

    Fabricating facts in a draft (e.g. confirming availability when the system
    does not know) creates legal and reputational risk for the property manager.
    """
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "2BR availability",
        "body": "Is the two bedroom unit still available?",
    })
    assert result.route == "auto_draft"
    assert result.draft is not None
    body_lower = result.draft.body.lower()
    # Draft must not assert availability, price, or a specific date
    for fabricated_claim in ("available", "price", "rent", "$", "move in", "move-in"):
        assert fabricated_claim not in body_lower, (
            f"Draft body fabricated a claim: found '{fabricated_claim}'"
        )
