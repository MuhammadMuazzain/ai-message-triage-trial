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
