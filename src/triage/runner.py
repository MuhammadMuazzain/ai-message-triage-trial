from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from .core import triage_message


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python -m triage.runner data/sample_messages.jsonl", file=sys.stderr)
        return 2

    path = Path(argv[0])
    total = 0
    correct = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        message = json.loads(line)
        result = triage_message(message)
        total += 1
        expected = message.get("expected_route")
        correct += int(expected == result.route)
        print(json.dumps({
            "id": message.get("id"),
            "expected": expected,
            "route": result.route,
            "category": result.category,
            "confidence": result.confidence,
            "warnings": result.warnings,
        }, sort_keys=True))

    if total:
        print(json.dumps({"accuracy": correct / total, "correct": correct, "total": total}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
