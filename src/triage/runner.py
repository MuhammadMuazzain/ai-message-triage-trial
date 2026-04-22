# =============================================================================
# CHANGES ADDED TO THIS FILE (relative to original client baseline):
#
# 1. logger = logging.getLogger(__name__) added so runner has its own named
#    logger (reuses the existing basicConfig setup, no new library needed).
#
# 2. json.loads(line) wrapped in try/except json.JSONDecodeError - bad lines
#    are logged as "skipped_invalid_line" and skipped; run never crashes.
#
# 3. triage_message(message) wrapped in try/except Exception - unexpected
#    failures are logged as "triage_failed" with message_id and error; run
#    never crashes.
#
# 4. JSON output extended with an "extraction" key exposing all six
#    structured-extraction fields per message.
#
# 5. --report flag added: suppresses per-message output and prints a
#    human-readable evaluation report with per-category accuracy, urgency
#    distribution, unit-mention extraction hit rate, and a safety check
#    for high-urgency messages that routed to auto_draft.
#
# 6. (fix 3) In --report mode the root logger level is raised to WARNING so
#    INFO routing logs (routed_to_human_review, routed_to_auto_draft, etc.)
#    do not clutter the human-readable report. WARNING and ERROR events
#    (bad JSON lines, unexpected triage failures) still print because those
#    signal real problems the operator needs to see even during a report run.
# =============================================================================

from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

from .core import triage_message


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print(
            "Usage: python -m triage.runner data/sample_messages.jsonl [--report]",
            file=sys.stderr,
        )
        return 2

    # --- NEW: --report flag triggers evaluation report mode ---
    report_mode = "--report" in argv
    path_args = [a for a in argv if a != "--report"]
    if not path_args:
        print("Error: no data file specified.", file=sys.stderr)
        return 2

    # --- NEW (fix 3): suppress INFO logs in report mode ---
    # basicConfig sets the root logger to INFO so routing events from core.py
    # print interleaved with the report output, making it unreadable.
    # Raising to WARNING keeps the report clean while still surfacing real
    # problems (skipped lines, triage failures) that the operator needs to see.
    if report_mode:
        logging.getLogger().setLevel(logging.WARNING)
    # --- END NEW ---


    path = Path(path_args[0])
    total = 0
    correct = 0

    # --- NEW: accumulators for the evaluation report ---
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
    urgency_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    high_urgency_auto_drafts: list[dict] = []
    unit_mentions_found: int = 0 # Tracks extraction hit rate
    # --- END NEW ---

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        # --- NEW: guard against malformed JSON lines; log and skip rather than crash ---
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("skipped_invalid_line", extra={"line": line[:80]})
            continue
        # --- END NEW ---
        # --- NEW: guard against unexpected triage errors; log and continue rather than crash ---
        try:
            result = triage_message(message)
        except Exception as e:
            logger.error("triage_failed", extra={"message_id": message.get("id"), "error": str(e)})
            continue
        # --- END NEW ---

        total += 1
        expected = message.get("expected_route")
        is_correct = int(expected == result.route)
        correct += is_correct
        ex = result.extraction

        # --- NEW: accumulate stats for report mode ---
        by_category[result.category]["total"] += 1
        by_category[result.category]["correct"] += is_correct
        urgency_dist[ex.urgency] = urgency_dist.get(ex.urgency, 0) + 1

        if ex.unit_mention is not None:
            unit_mentions_found += 1

        if ex.urgency == "high" and result.route == "auto_draft":
            high_urgency_auto_drafts.append({
                "id": message.get("id"),
                "subject": message.get("subject", ""),
                "urgency": ex.urgency,
                "route": result.route,
            })
        # --- END NEW ---

        if not report_mode:
            print(json.dumps({
                "id": message.get("id"),
                "expected": expected,
                "route": result.route,
                "category": result.category,
                "confidence": result.confidence,
                "warnings": result.warnings,
                # --- NEW: extraction block added to output ---
                "extraction": {
                    "sender_type": ex.sender_type,
                    "urgency": ex.urgency,
                    "requested_action": ex.requested_action,
                    "unit_mention": ex.unit_mention,
                    "callback_number": ex.callback_number,
                    "property_name": ex.property_name,
                    # --- NEW (product improvement): plain-English summary ---
                    "reviewer_summary": ex.reviewer_summary,
                },
                # --- END NEW ---
            }, sort_keys=True))

    if total:
        if report_mode:
            # --- NEW: human-readable evaluation report ---
            accuracy_pct = round(correct / total * 100, 1)
            sep = "=" * 52

            print(sep)
            print("  TRIAGE EVALUATION REPORT")
            print(sep)
            print(f"  Messages processed : {total}")
            print(f"  Correctly routed   : {correct} / {total}")
            print(f"  Overall accuracy   : {accuracy_pct}%")
            print()


            print("  ACCURACY BY CATEGORY")
            print("  " + "-" * 48)
            for cat, v in sorted(by_category.items()):
                cat_pct = round(v["correct"] / v["total"] * 100, 1) if v["total"] else 0
                bar = "#" * int(cat_pct // 10)
                print(f"  {cat:<20} {v['correct']:>2}/{v['total']:<2}  {cat_pct:>5}%  {bar}")
            print()

            print("  URGENCY DISTRIBUTION")
            print("  " + "-" * 48)
            for level in ("high", "medium", "low"):
                count = urgency_dist.get(level, 0)
                bar = "#" * count
                print(f"  {level:<10} {count:>3} messages   {bar}")
            print()

            print(f"  Unit mentions extracted : {unit_mentions_found} / {total} messages")
            print()

            print("  SAFETY CHECK - High-urgency messages sent to auto-draft")
            print("  " + "-" * 48)
            if high_urgency_auto_drafts:
                print("  WARNING: the following messages had urgency=high but")
                print("  were auto-drafted instead of routed to human review.")
                print()
                for item in high_urgency_auto_drafts:
                    print(f"    [{item['id']}] {item['subject']}")
            else:
                print("  OK - no high-urgency messages slipped to auto-draft.")
            print(sep)
            # --- END NEW ---
        else:
            print(json.dumps({
                "accuracy": correct / total,
                "correct": correct,
                "total": total,
            }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
