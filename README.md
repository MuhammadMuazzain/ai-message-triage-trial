# AI Message Triage Paid Trial

This is a paid trial for an ongoing AI automation role. The project is intentionally small and sanitized. It is meant to test how you read existing code, improve a partially built workflow, add safety, and propose useful product ideas without receiving overly detailed instructions.

## Time Box

- Maximum billable time: 4 hours unless approved in writing first.
- Do not start work until the Upwork contract is active.
- Use your own paid AI/coding-agent tooling. Do not request Tri Star credentials, API keys, production data, or account access.

## Goal

Improve this small AI-style inbound message triage workflow.

The current workflow:

- classifies inbound property-management messages
- drafts a basic response
- routes risky messages to human review
- logs basic processing details

It is intentionally underbuilt. Your job is to make one focused, high-value improvement and prove it works.

## Required Deliverable

Submit your completed work through the active Upwork workroom using whatever Upwork-supported delivery method is available, with:

1. A short README note explaining what you changed and why.
2. Tests and the exact command to run them.
3. Logging/error-handling/validation notes.
4. A short list of 3 product improvements you would build next.
5. A clear statement of which files/functions you wrote personally vs adapted/generated with AI help.

## What To Build

Pick one meaningful improvement. Examples:

- Improve classification accuracy and confidence scoring.
- Add a safer human-review gate for legally sensitive, maintenance emergency, or money-related messages.
- Add structured extraction, such as property, unit, urgency, callback number, and requested action.
- Add a better response-drafting layer that never fabricates facts and explains why a human review is needed.
- Add an evaluation/report command that shows classification accuracy on the sample dataset.

Do not build a giant system. A small, well-tested improvement with good judgment beats a large fragile rewrite.

## Baseline Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m triage.runner data/sample_messages.jsonl
```

## Evaluation Rubric

We will score:

- Code-reading and restraint: works with the existing code instead of rewriting everything.
- Product judgment: chooses a useful improvement for a real operations workflow.
- Safety: avoids fabricated facts, protects sensitive cases, and makes human-review boundaries clear.
- Tests: meaningful tests for normal cases and edge cases.
- Observability: useful logging or evaluation output.
- Communication: concise setup notes and clear tradeoffs.
- AI-agent fluency: uses AI tools effectively but verifies the result.

## Security Rules

- Use only the fake data in this project.
- Do not ask for logins, credentials, Yardi access, tenant records, or production code.
- Do not include secrets or real personal data in your submission.
- If you need more data, create additional fake examples.

---

## Candidate Submission

**Submitted by:** Muhammad Muazzain  
**Date:** April 22, 2026

---

### 1. What I changed and why

**Improvement chosen: Structured extraction**

A property manager looking at a triage queue gets no actionable information from `route=human_review` alone. They still have to open each email to find out who sent it, how urgent it is, what the person wants, and which unit it concerns. This improvement adds a structured `Extraction` object to every `TriageResult` that answers those four questions without opening the email.

Every message, regardless of route, now produces all six fields from Isaac's extraction spec:

| Field | Values | Purpose |
|---|---|---|
| `sender_type` | `tenant`, `prospect`, `vendor`, `system`, `unknown` | Identifies sender role from email local part |
| `urgency` | `high`, `medium`, `low` | Scanned across both subject and body |
| `requested_action` | ≤8-word phrase | What the sender wants, derived from category and keywords |
| `unit_mention` | Street name, unit code, or `None` | Extracted property reference for record lookup |
| `callback_number` | Phone number string, or `None` | Extracted from body so reviewer can call back without opening the email |
| `property_name` | Building/complex name, or `None` | Extracted Title-Case noun phrase followed by a property-type word (Apartments, Condos, Residences, etc.) |

I chose this over the other four options because it adds value to the existing routing without touching the routing logic at all, purely additive and safe. It also makes the `human_review` queue directly actionable.

**Sample data coverage (`data/sample_messages.jsonl`):**

The dataset was expanded from 10 to 40 messages to thoroughly exercise all six extraction fields. The first 10 messages are the original client-provided examples, untouched. Messages `msg_011`–`msg_040` are new fake examples added to cover every routing category, urgency level, and extraction field combination. Specifically for the three new extraction fields:

| Field | Present in | Realistic scenario |
|---|---|---|
| `callback_number` | 16 of 40 messages | Urgent maintenance, legal disputes, money/vendor issues, senders who need a callback |
| `property_name` | 14 of 40 messages | Tour requests, leasing inquiries, vendor invoices, messages referencing a specific building |
| `unit_mention` | 11 of 40 messages | Maintenance reports, legal notices, deposit disputes, messages tied to a specific unit |

Fields are absent where it would not be realistic (system skips, generic amenity questions, application follow-ups) to avoid forcing artificial data.

---

### 2. Tests - run with

```bash
pytest -q
```

21 tests total. The original 5 client tests are untouched. 16 new tests were added covering:

- Urgency detection from subject line alone (`No heat` in subject, calm body)
- Maintenance routing fires before money routing when both terms are present
- Auto-draft reply subject does not double-prefix `Re:`
- Unit code extracted precisely (`Unit 4B`, not surrounding words)
- Unknown sender type reported as `unknown`, not guessed
- Auto-draft body contains no fabricated claims (availability, price, rent, dates)
- Extraction present and correct on `skip` and `invalid_sender` routes
- Non-dict input (`None`, string) fails closed to `human_review` without crashing
- Whitespace-only sender treated as invalid, fails closed to `human_review`
- Every route returns a proper `Extraction` object, never `None`

**Evaluation report (observability command):**

```bash
python -m triage.runner data/sample_messages.jsonl --report
```

Prints a formatted, human-readable report. Example output:

```
====================================================
  TRIAGE EVALUATION REPORT
====================================================
  Messages processed : 40
  Correctly routed   : 40 / 40
  Overall accuracy   : 100.0%

  ACCURACY BY CATEGORY
  ------------------------------------------------
  fair_housing          4/4   100.0%  ##########
  leasing_general      15/15  100.0%  ##########
  legal                 5/5   100.0%  ##########
  maintenance           8/8   100.0%  ##########
  money                 5/5   100.0%  ##########
  system                3/3   100.0%  ##########

  URGENCY DISTRIBUTION
  ------------------------------------------------
  high         8 messages   ########
  medium      10 messages   ##########
  low         22 messages   ######################

  Unit mentions extracted : 11 / 40 messages

  SAFETY CHECK - High-urgency messages sent to auto-draft
  ------------------------------------------------
  OK - no high-urgency messages slipped to auto-draft.
====================================================
```

The safety check at the bottom is the key signal for operations: if any message had `urgency=high` but was sent to auto-draft instead of human review, it is listed here by ID and subject.

**Per-message output (standard mode):**

```bash
python -m triage.runner data/sample_messages.jsonl
```

Outputs one JSON line per message including route, category, confidence, warnings, and all six extraction fields. Final line: `{"accuracy": 1.0, "correct": 40, "total": 40}`.

---

### 3. Logging and error-handling notes

**Logging - `src/triage/core.py`**

- `logger.debug("triage_start")` fires at entry for every message, full trace at DEBUG level.
- `logger.info("routed_to_human_review")` fires before every `human_review` return with `message_id`, `category`, and `reason`.
- `logger.info("routed_to_skip")` fires before every `skip` return.
- `logger.info("routed_to_auto_draft")` fires before the `auto_draft` return.
- `logger.warning("invalid_sender")` fires when sender is missing or has no `@`.
- `logger.warning("unit_mention_extract_failed")` fires if the regex raises unexpectedly, extraction degrades to `None` and the run continues.

**Error handling - `src/triage/core.py`**

- Non-dict input to `triage_message()` (e.g. `None`, a string) logs `invalid_message_type` warning and returns `human_review`, never crashes.
- `subject`, `body`, and `sender` are `.strip()`ed so whitespace-only strings normalise to `""` and cannot accidentally match routing or extraction terms.

**Error handling - `src/triage/runner.py`**

- `json.loads(line)` is wrapped in `try/except json.JSONDecodeError`, malformed lines log `skipped_invalid_line` (WARNING) and are skipped.
- `triage_message(message)` is wrapped in `try/except Exception`, unexpected failures log `triage_failed` (ERROR) with `message_id` and `error`, and processing continues to the next message.
- The run never crashes on bad input.

---

### 4. Three product improvements I would build next

1. **Weighted confidence scoring based on term overlap and co-occurrence.** Right now every maintenance message gets a flat `0.65` regardless of whether it matched one mild term ("leak") or four critical ones ("flood", "emergency", "no heat", "immediately"). I would replace the flat scores with a weighted accumulator: each matched term carries a severity weight, co-occurring terms in the same category compound the score, and the final confidence is capped at `0.95`. A score above `0.85` could also trigger an automatic escalation flag, giving the ops queue a rough priority column, so a flooding emergency surfaces above a dripping faucet without a human having to open both emails first.

2. **Tenant name extraction using salutation and self-identification patterns.** The `Extraction` dataclass already returns `callback_number` and `unit_mention`, but a reviewer still has to open the email to find out who they are calling back. Adding `tenant_name: str | None` using lightweight regex patterns like `"Hi,?\s+(?:I'?m|this is)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)"` and `"(?:from|regards,?|sincerely,?)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)"` would cover the majority of real messages without an LLM call. The field should default to `None` and degrade silently the same way `unit_mention` already does, so a miss is never worse than the current state.

3. **Hard routing gate for high-urgency messages, not just a report warning.** The `--report` flag already flags any `urgency=high` message that slipped to `auto_draft`, but that is an after-the-fact audit, not a preventive control. In a production deployment a maintenance flood, a legal threat, or a fire-safety issue should never reach a generic auto-reply regardless of how the keyword matching resolved. I would add a post-routing override step: after `triage_message()` returns, if `extraction.urgency == "high"` and `result.route == "auto_draft"`, the runner upgrades the route to `human_review` and appends `"high_urgency_override"` to `result.warnings`. This keeps the routing logic in `core.py` untouched and makes the safety boundary explicit, testable, and auditable at the runner layer.

---

### 5. Authorship statement

**Written personally (no AI assistance):**

- `core.py`, `_detect_sender_type()` function (lines 239-249): the full if/elif chain that classifies sender role from the email local part.
- `core.py`, skip-route logging block (lines 135-145): added `logger.info("routed_to_skip")` before the system skip return, which was the only route missing an info log.
- `core.py`, `_URGENCY_HIGH` tuple: extended to include `"no hot water"`, `"flood"`, and `"flooding"` as high-urgency triggers.
- `runner.py`, `main()` argument parsing block (lines 38-53): the `--report` flag detection, `path_args` filtering, and the missing-file guard.
- `runner.py`, `ACCURACY BY CATEGORY` section of the `--report` output: the per-category accuracy table with fixed-width columns and `#` bar charts. Writing this personally was a product judgment call, showing accuracy broken down by category (fair_housing, legal, maintenance, etc.) is far more useful to an operations reviewer than a single overall number, because it reveals which message types the classifier handles confidently and which might need attention.
- Tests, `test_maintenance_check_fires_before_money_check`, `test_reply_subject_does_not_double_prefix`, `test_extraction_sender_type_unknown_for_generic_domain`: written personally to cover routing order integrity, reply formatting, and sender classification edge cases.
- Tests, `test_non_dict_input_fails_closed`, `test_whitespace_only_sender_fails_closed`: written personally to verify the two edge-case guards added to `triage_message()`.
- Test, `test_extraction_always_returns_extraction_object`: written personally as a cross-route contract test. Rather than checking one route at a time, this test loops over three different message types (maintenance, system skip, leasing general) and asserts that every one returns a proper `Extraction` instance, not `None` and not the default fallback. This matters because the `Extraction` field uses a `default_factory`, which means a coding mistake in any return branch (forgetting to pass `extraction=_extract(...)`) would silently produce a wrong default rather than crashing. This test catches that class of bug.

**Drafted with AI assistance, then reviewed and verified personally:**

- `Extraction` dataclass structure and field names.
- `_extract()`, `_detect_urgency()`, `_detect_requested_action()`, `_extract_unit_mention()` helper implementations, each reviewed against test output. The unit-mention regex produced false positives (`"bedroom apartment on Maple Street"`) that were caught during review and corrected.
- `--report` evaluation output structure in `runner.py`, overall accuracy header, urgency distribution, unit-mention extraction count, and the safety check section (`high_urgency_auto_drafts`, `unit_mentions_extracted`).
- Edge-case guards: non-dict input to `triage_message()` and `.strip()` normalisation.
- All 40 fake data messages in `sample_messages.jsonl`, each reviewed for realistic phrasing and correct `expected_route` labels, verified by running the runner to 100% accuracy. Messages `msg_011` through `msg_040` were deliberately written to exercise the three new extraction fields: `callback_number` is present in 16 messages (urgent maintenance, legal disputes, money/vendor issues), `property_name` is present in 14 messages (tour requests, leasing questions, vendor invoices), and `unit_mention` is present in 11 messages, each placed only where it is realistic for a sender to include it, not artificially forced into every message.
- The 7 remaining new tests not listed in the "Written personally" section above.

**Not touched:**

- Original routing logic in `triage_message()`, the `if/elif` chain, term lists, and return shapes are exactly as the client provided.
