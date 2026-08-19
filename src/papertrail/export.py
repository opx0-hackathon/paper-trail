"""Rendering a memory file and its ledger into something portable."""

from __future__ import annotations

from datetime import UTC, datetime

from papertrail.models import Memory, Receipt


def as_json(memories: list[Memory], receipts: list[Receipt], holder: str) -> dict[str, object]:
    return {
        "format": "papertrail.v1",
        "holder": holder,
        "exported_at": datetime.now(UTC).isoformat(),
        "memories": [
            {
                "path": m.path,
                "value": m.value,
                "note": m.note,
                "attested": m.attested,
                "sensitive": m.sensitive,
                "revoked": m.revoked,
                "source": m.source,
                "created_at": m.created_at,
            }
            for m in memories
        ],
        "ledger": [r.as_dict() for r in receipts],
    }


def as_markdown(memories: list[Memory], receipts: list[Receipt], holder: str) -> str:
    """A memory file a person can read, paste into another assistant, or keep."""
    stamped = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# {holder}'s memory file", "", f"Exported {stamped} from Paper Trail.", ""]

    live = [m for m in memories if not m.revoked]
    gone = [m for m in memories if m.revoked]

    for memory in live:
        flags = " ".join(
            f"`{flag}`"
            for flag, on in (("proof only", memory.attested), ("special", memory.sensitive))
            if on
        )
        lines.append(f"## {memory.note}{'  ' + flags if flags else ''}")
        lines.append("")
        lines.append(memory.value)
        lines.append("")
        lines.append(f"_{memory.path} · {memory.source}_")
        lines.append("")

    if gone:
        lines += ["## Revoked", ""]
        lines += [f"- `{m.path}` — {m.note}" for m in gone]
        lines.append("")

    lines += ["## Ledger", "", "| when | what | memory | reason |", "|---|---|---|---|"]
    for receipt in receipts:
        when = datetime.fromtimestamp(receipt.created_at, UTC).strftime("%H:%M:%S")
        reason = (receipt.purpose or receipt.detail).replace("|", "\\|")
        lines.append(f"| {when} | {receipt.action} | `{receipt.path}` | {reason} |")

    return "\n".join(lines) + "\n"
