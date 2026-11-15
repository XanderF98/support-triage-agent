"""Measure the redactor against the labeled tickets in data/tickets.jsonl.

For each labeled personal detail, the detail counts as caught only if the
redactor's spans cover it completely. Anything the redactor flags that
overlaps no label counts as a false positive.

Run from the repository root:  python evals/run_deid_eval.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from deid import detected  # noqa: E402


def covered(start: int, end: int, spans: list[dict]) -> bool:
    """True if every character in start..end falls inside some detected span."""
    return all(any(s["start"] <= i < s["end"] for s in spans) for i in range(start, end))


def main() -> int:
    tickets = [json.loads(line) for line in (ROOT / "data" / "tickets.jsonl").read_text().splitlines() if line]
    labeled, caught, misses, false_positives = defaultdict(int), defaultdict(int), [], []

    for ticket in tickets:
        body = ticket["body"]
        spans = detected(body, known_names=[ticket["customer_name"]])
        label_ranges = []
        for label in ticket["pii"]:
            start = body.index(label["text"])
            end = start + len(label["text"])
            label_ranges.append((start, end))
            labeled[label["type"]] += 1
            if covered(start, end, spans):
                caught[label["type"]] += 1
            else:
                misses.append((ticket["id"], label["type"], label["text"]))
        for span in spans:
            if not any(span["start"] < end and start < span["end"] for start, end in label_ranges):
                false_positives.append((ticket["id"], span["type"], span["text"]))

    total_labeled, total_caught = sum(labeled.values()), sum(caught.values())
    flagged = total_caught + len(false_positives)

    print(f"Tickets: {len(tickets)}   Labeled details: {total_labeled}\n")
    print("| Type | Labeled | Caught | Recall |")
    print("|---|---|---|---|")
    for kind in sorted(labeled):
        print(f"| {kind} | {labeled[kind]} | {caught[kind]} | {caught[kind] / labeled[kind]:.0%} |")
    print(f"| **All** | **{total_labeled}** | **{total_caught}** | **{total_caught / total_labeled:.0%}** |")
    print(f"\nPrecision: {total_caught}/{flagged} = {total_caught / flagged:.0%}")

    print("\nMissed:")
    for ticket_id, kind, text in misses:
        print(f"  {ticket_id}  {kind:<10} {text}")
    print("\nFalse positives:")
    for ticket_id, kind, text in false_positives:
        print(f"  {ticket_id}  {kind:<10} {text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
