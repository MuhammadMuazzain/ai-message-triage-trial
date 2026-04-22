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


# ---------------------------------------------------------------------------
# Fix 1: whole-word keyword matching in _detect_requested_action
# ---------------------------------------------------------------------------

def test_requested_action_please_does_not_trigger_lease():
    """'please' contains 'lease' as a substring.

    Before the fix, bare `in` matching caused "please confirm payment" to
    return 'ask about lease term renewal or dates'. After the fix, \b word
    boundaries ensure only the complete word 'lease' fires the lease branch.
    """
    result = triage_message({
        "sender": "vendor@example.com",
        "subject": "Payment",
        "body": "Please confirm payment has been sent.",
    })
    # Must not match the lease branch due to 'please' containing 'lease'
    assert result.extraction.requested_action != "ask about lease term renewal or dates"


def test_requested_action_unavailable_does_not_trigger_tour():
    """'unavailable' contains 'available' as a substring.

    Before the fix, a message saying the unit is 'unavailable' would
    incorrectly return 'schedule apartment tour or check availability'.
    After the fix, only the standalone word 'available' fires the tour branch.
    """
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Unit status",
        "body": "I was told the unit is currently unavailable. Is anything else open?",
    })
    # Must not match the tour/availability branch due to 'unavailable' containing 'available'
    assert result.extraction.requested_action != "schedule apartment tour or check availability"


# ---------------------------------------------------------------------------
# Fix 2: urgency false positives - conditional high-urgency terms
# ---------------------------------------------------------------------------





def test_urgency_tour_today_is_not_high():
    """'today' in a routine leasing/tour request must not produce urgency=high.

    Before the fix, 'can I tour today?' was classified high urgency because
    'today' was an unconditional high-urgency keyword. After the fix, 'today'
    and 'now' are conditional: they only fire high urgency outside
    leasing_general so routine scheduling phrases are not treated as
    emergencies.
    """
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Tour request",
        "body": "Can I schedule a tour today? I am very interested in the unit.",
    })
    assert result.route == "auto_draft"
    # 'today' in a leasing context must not produce high urgency
    assert result.extraction.urgency != "high"


def test_urgency_today_is_still_high_for_maintenance():
    """'today' must still produce urgency=high when the message is a maintenance issue.

    This confirms the conditional logic does not suppress urgency for the
    categories where time pressure genuinely matters.
    """
    result = triage_message({
        "sender": "tenant@example.com",
        "subject": "No hot water",
        "body": "There is no hot water in my unit. Please send someone today.",
    })
    assert result.route == "human_review"
    assert result.extraction.urgency == "high"


# ---------------------------------------------------------------------------
# Fix 3: INFO logs must not clutter --report output
# ---------------------------------------------------------------------------

def test_report_mode_suppresses_info_logs(tmp_path, capsys):
    """In --report mode the root logger must be raised to WARNING so INFO
    routing events (routed_to_human_review, routed_to_auto_draft, etc.) do
    not interleave with the human-readable report on stdout/stderr.

    We write a minimal one-message JSONL file, run main() with --report, then
    assert that no 'INFO' token appears in the combined output. WARNING and
    ERROR events are still allowed because those signal real problems.
    """
    import logging
    from triage.runner import main

    # Write a minimal valid JSONL fixture
    data = tmp_path / "msgs.jsonl"
    data.write_text(
        '{"id":"t1","sender":"prospect@example.com","subject":"Parking",'
        '"body":"Is parking included?","expected_route":"auto_draft"}\n',
        encoding="utf-8",
    )

    # Reset root logger level before the call so the test is isolated
    logging.getLogger().setLevel(logging.INFO)

    main([str(data), "--report"])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # No INFO-level routing log lines should appear in either stream
    assert "INFO" not in combined, (
        "INFO log lines leaked into --report output: " + combined
    )


# ---------------------------------------------------------------------------
# Product improvement: reviewer_summary field
# ---------------------------------------------------------------------------

def test_reviewer_summary_high_urgency_maintenance():
    """High-urgency maintenance message must produce a summary that includes
    the urgency level, sender type, and unit mention so a reviewer can triage
    the queue at a glance without opening the original email.
    """
    result = triage_message({
        "sender": "tenant@example.com",
        "subject": "Flood in bathroom",
        "body": (
            "There is a flood in the bathroom right now at Riverside Apartments, "
            "unit 2A. This is an emergency. Please call me at (555) 308-1247."
        ),
    })
    summary = result.extraction.reviewer_summary
    assert summary, "reviewer_summary must not be empty"
    # Summary must surface urgency and sender role
    assert "High" in summary
    assert "tenant" in summary
    # Unit mention must be included in the summary when present
    assert "unit 2A" in summary or "2A" in summary

def test_reviewer_summary_low_urgency_leasing():
    """Generic prospect leasing inquiry with no unit or callback must produce
    a summary that correctly reflects low urgency and reports no contact info,
    so the reviewer knows immediately this message needs no urgent action.
    """
    result = triage_message({
        "sender": "prospect@example.com",
        "subject": "Parking question",
        "body": "Is parking included with the apartment?",
    })
    summary = result.extraction.reviewer_summary
    assert summary, "reviewer_summary must not be empty"
    assert "Low" in summary
    assert "prospect" in summary
    # No unit or callback in this message
    assert "No unit or callback on file" in summary