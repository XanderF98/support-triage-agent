"""De-identify support ticket text before it is sent to a language model.

The redactor replaces personal details with typed placeholders such as
[EMAIL_1] or [NAME_2], and keeps a mapping so the placeholders in a drafted
reply can be swapped back for the real values afterwards:

    redacted, mapping = redact(ticket_text, known_names=["Dana Whitfield"])
    draft = call_model(redacted)            # the model never sees real details
    reply = restore(draft, mapping)

Detection is rule-based. Patterns catch structured details (emails, phone
numbers, card numbers, IDs, dates). Names are matched from the names already
on the ticket record, plus a few "my name is ..." style phrases. See the
README for what this approach misses.
"""

import re
from dataclasses import dataclass, field

# Order matters: earlier patterns win when two patterns match the same text.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?!\w)")),
    ("MEMBER_ID", re.compile(r"\bTW-\d{6}\b")),
    ("DATE", re.compile(
        r"\b(?:\d{1,2}/\d{1,2}/\d{2,4}"
        r"|\d{4}-\d{2}-\d{2}"
        r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? \d{4})\b"
    )),
    ("ADDRESS", re.compile(
        r"\b\d{1,6} (?:[A-Z][a-z]+ ){1,3}"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Court|Ct|Place|Pl)\b\.?"
    )),
]

# Phrases that introduce a name the ticket record may not contain.
NAME_INTRO = re.compile(
    r"\b(?:my name is|this is|I am|I'm|on behalf of|[Mm]y (?:husband|wife|partner|son|daughter|mother|father),?)"
    r" ((?:[A-Z][a-z]+)(?: [A-Z][a-z]+)?)"
)

# Capitalized words that follow "I'm" or "I am" but are not names.
NOT_NAMES = {
    "Sorry", "Writing", "Trying", "Calling", "Still", "Not", "Having", "Unable",
    "Confused", "Worried", "Frustrated", "Asking", "Looking", "Hoping", "Waiting",
}


@dataclass
class Mapping:
    """Placeholder-to-original lookup produced by redact()."""

    values: dict[str, str] = field(default_factory=dict)
    _by_original: dict[tuple[str, str], str] = field(default_factory=dict)
    _counts: dict[str, int] = field(default_factory=dict)

    def placeholder(self, kind: str, original: str) -> str:
        """Return the placeholder for a value, reusing it if the value was seen before."""
        key = (kind, original.lower())
        if key not in self._by_original:
            self._counts[kind] = self._counts.get(kind, 0) + 1
            token = f"[{kind}_{self._counts[kind]}]"
            self._by_original[key] = token
            self.values[token] = original
        return self._by_original[key]


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _find_spans(text: str, known_names: list[str]) -> list[tuple[int, int, str]]:
    """Return non-overlapping (start, end, kind) spans, earliest first."""
    candidates: list[tuple[int, int, str]] = []

    for kind, pattern in PATTERNS:
        for m in pattern.finditer(text):
            if kind == "CARD":
                digits = re.sub(r"\D", "", m.group())
                if not (13 <= len(digits) <= 19 and _luhn_valid(digits)):
                    continue
            candidates.append((m.start(), m.end(), kind))

    # Names from the ticket record: the full name, then each part on its own.
    name_parts: list[str] = []
    for name in known_names:
        name_parts.append(name)
        name_parts.extend(part for part in name.split() if len(part) > 2)
    for part in sorted(set(name_parts), key=len, reverse=True):
        for m in re.finditer(rf"\b{re.escape(part)}\b", text, flags=re.IGNORECASE):
            candidates.append((m.start(), m.end(), "NAME"))

    for m in NAME_INTRO.finditer(text):
        if m.group(1).split()[0] not in NOT_NAMES:
            candidates.append((m.start(1), m.end(1), "NAME"))

    # Keep the earliest span; on a tie keep the longest; drop anything that overlaps a kept span.
    priority = {kind: i for i, (kind, _) in enumerate(PATTERNS)}
    candidates.sort(key=lambda s: (s[0], -(s[1] - s[0]), priority.get(s[2], 99)))
    spans: list[tuple[int, int, str]] = []
    for span in candidates:
        if not spans or span[0] >= spans[-1][1]:
            spans.append(span)
    return spans


def redact(text: str, known_names: list[str] | None = None) -> tuple[str, Mapping]:
    """Replace personal details in text with placeholders.

    known_names are names already on the ticket record, such as the customer's.
    Returns the redacted text and the mapping needed to restore it.
    """
    mapping = Mapping()
    out, cursor = [], 0
    for start, end, kind in _find_spans(text, known_names or []):
        out.append(text[cursor:start])
        out.append(mapping.placeholder(kind, text[start:end]))
        cursor = end
    out.append(text[cursor:])
    return "".join(out), mapping


def restore(text: str, mapping: Mapping) -> str:
    """Swap placeholders in text back for the original values."""
    return re.sub(r"\[[A-Z_]+_\d+\]", lambda m: mapping.values.get(m.group(), m.group()), text)


def detected(text: str, known_names: list[str] | None = None) -> list[dict]:
    """List what would be redacted, with character positions. Used by the evaluation."""
    return [
        {"type": kind, "text": text[start:end], "start": start, "end": end}
        for start, end, kind in _find_spans(text, known_names or [])
    ]
