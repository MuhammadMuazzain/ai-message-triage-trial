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
