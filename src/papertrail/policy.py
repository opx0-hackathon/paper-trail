"""Every authorization decision, as pure functions over memories and a request."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from papertrail.models import ErrorCode, Memory, PaperTrailError, ReceiptAction, Stamp


def validate_request(requested: Sequence[str], known: Mapping[str, Memory]) -> list[str]:
    """Accept only if every path is a live memory and no special category rides along."""
    paths = _unique(requested)
    if not paths:
        raise PaperTrailError(ErrorCode.EMPTY_REQUEST, "a request must name at least one memory")
    unknown = [path for path in paths if path not in known]
    if unknown:
        raise PaperTrailError(
            ErrorCode.UNKNOWN_FIELDS, f"not in this memory file: {', '.join(unknown)}"
        )
    revoked = [path for path in paths if known[path].revoked]
    if revoked:
        raise PaperTrailError(ErrorCode.REVOKED, f"revoked by the holder: {', '.join(revoked)}")
    sensitive = [path for path in paths if known[path].sensitive]
    if sensitive and len(sensitive) != len(paths):
        raise PaperTrailError(
            ErrorCode.MIXED_SENSITIVE,
            f"a special category needs a request of its own: {', '.join(sensitive)}",
        )
    return paths


def split_by_category(
    paths: Sequence[str], known: Mapping[str, Memory]
) -> tuple[list[str], list[str]]:
    """The ordinary memories and the special categories, as the two requests they are."""
    unique = _unique(paths)
    ordinary = [p for p in unique if p in known and not known[p].sensitive]
    special = [p for p in unique if p in known and known[p].sensitive]
    return ordinary, special


def authorize_share(paths: Sequence[str], known: Mapping[str, Memory]) -> list[str]:
    """Paths a link may carry: live memories only, and never a special category.

    A link is handed to someone the holder cannot supervise, so the rule is stricter than
    a request: a special category is not shareable at all, not merely shareable apart.
    """
    wanted = _unique(paths)
    if not wanted:
        raise PaperTrailError(ErrorCode.EMPTY_REQUEST, "a link must cover at least one memory")
    unknown = [p for p in wanted if p not in known or known[p].revoked]
    if unknown:
        raise PaperTrailError(
            ErrorCode.UNKNOWN_FIELDS, f"not available to share: {', '.join(unknown)}"
        )
    special = [p for p in wanted if known[p].sensitive]
    if special:
        raise PaperTrailError(
            ErrorCode.MIXED_SENSITIVE,
            f"a special category never travels on a link: {', '.join(special)}",
        )
    return wanted


def project(memories: Sequence[Memory]) -> dict[str, object]:
    """The only route a value takes to a model: attested yields proof, never value."""
    context: dict[str, object] = {}
    for memory in memories:
        if not memory.attested:
            context[memory.path] = memory.value
            continue
        prefix, _, _ = memory.path.rpartition(".")
        context[f"{prefix}.confirmed" if prefix else "confirmed"] = True
    return context


def labels_for_scope(memories: Sequence[Memory]) -> list[dict[str, str]]:
    """What the scoping model may see: what each memory is about, never what it holds."""
    return [{"path": m.path, "about": m.note} for m in memories if not m.revoked]


def stamps(memories: Sequence[Memory], purposes: Mapping[str, str]) -> list[Stamp]:
    return [
        Stamp(
            path=memory.path,
            note=memory.note,
            purpose=purposes.get(memory.path, ""),
            kind="proof" if memory.attested else "value",
        )
        for memory in memories
    ]


def read_action(memories: Sequence[Memory]) -> ReceiptAction:
    if any(memory.sensitive for memory in memories):
        return ReceiptAction.SENSITIVE_READ
    return ReceiptAction.READ


def _unique(paths: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(paths))
