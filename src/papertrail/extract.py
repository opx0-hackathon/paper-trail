"""Turning arbitrary text a person pastes into candidate memories they can approve."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from papertrail.llm import SAFE_PATH, Client, json_list, load_prompt
from papertrail.models import Memory, MemorySource

MAX_INPUT = 20_000
MAX_CANDIDATES = 12
EXTRACT_TOKENS = 1400

SYSTEM = load_prompt("extract")


async def extract(client: Client, text: str, taken: Sequence[str]) -> list[Memory]:
    """Candidate memories from pasted text. Never writes; the holder approves each."""
    raw = await client.chat(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text[:MAX_INPUT]},
        ],
        EXTRACT_TOKENS,
        0.2,
        purpose="extract",
    )
    return parse(raw, taken)


def parse(raw: str, taken: Sequence[str]) -> list[Memory]:
    """Read the extraction reply, discarding anything that is not a plain new memory."""
    block = json_list(raw, "memories")
    if block is None:
        return []
    seen = set(taken)
    found: list[Memory] = []
    for item in block:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip().lower()
        value = str(item.get("value", "")).strip()
        note = str(item.get("note", "")).strip()
        if not SAFE_PATH.match(path) or path in seen or not value or not note:
            continue
        seen.add(path)
        found.append(
            Memory(
                path=path,
                value=value[:400],
                note=note[:80],
                attested=bool(item.get("attested")),
                sensitive=bool(item.get("sensitive")),
                source=str(MemorySource.IMPORTED),
            )
        )
        if len(found) == MAX_CANDIDATES:
            break
    return found


def fallback(text: str, taken: Sequence[str]) -> list[Memory]:
    """A keyword pass for when the model is unreachable, so import never simply fails."""
    topics = [
        (
            "diet.style",
            "what I eat and what I don't",
            r"\b(vegetarian|vegan|halal|kosher|pescatarian)\b",
        ),
        (
            "health.condition",
            "a diagnosed medical condition",
            r"\b(allergic|allergy|intolerant|diabetic|asthma)\b",
        ),
        (
            "work.role",
            "what I do for work",
            r"\b(engineer|developer|designer|student|teacher|researcher|founder)\b",
        ),
        ("location.city", "where I live", r"\b(live[sd]? in|based in|from)\s+([A-Z][a-z]+)"),
        (
            "work.stack",
            "what I build software with",
            r"\b(python|javascript|typescript|rust|go|java|react)\b",
        ),
    ]
    seen = set(taken)
    found: list[Memory] = []
    for path, note, pattern in topics:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match or path in seen:
            continue
        seen.add(path)
        sentence = _sentence_around(text, match.start())
        found.append(
            Memory(
                path=path,
                value=sentence[:400],
                note=note,
                sensitive=path.startswith("health."),
                source=str(MemorySource.IMPORTED),
            )
        )
    return found


def _sentence_around(text: str, index: int) -> str:
    start = max(text.rfind(".", 0, index), text.rfind("\n", 0, index)) + 1
    end = min(
        (i for i in (text.find(".", index), text.find("\n", index)) if i != -1),
        default=len(text),
    )
    return text[start : end + 1].strip() or text[index : index + 200].strip()


def preview(memories: Sequence[Memory]) -> str:
    return json.dumps([{"path": m.path, "note": m.note} for m in memories])
