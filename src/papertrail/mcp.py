"""The agent-facing surface: the same consent, receipts and revocation, over MCP.

An assistant somewhere else asks this file for context and gets exactly what the holder
has allowed, or a request the holder has to answer. Nothing here decides anything; policy
does, and the store stamps it.
"""

from __future__ import annotations

import time
from typing import Any

from papertrail import policy
from papertrail.models import Memory, PaperTrailError, ReceiptAction
from papertrail.store import Store

GRANT_TTL = 60 * 60
MAX_PATHS = 16


def describe(store: Store, session_id: str) -> dict[str, Any]:
    """What is available to ask for: subjects only, never values."""
    live = store.live(session_id)
    return {
        "memories": policy.labels_for_scope(live),
        "note": (
            "You are seeing what each memory is about, never what it holds. Call "
            "request_context with the paths you need and a purpose the holder will read."
        ),
    }


def request_context(
    store: Store, session_id: str, app: str, paths: list[str], purpose: str
) -> dict[str, Any]:
    """Projected values for anything a standing grant covers, or a pending request."""
    now = time.time()
    wanted = list(dict.fromkeys(paths))[:MAX_PATHS]
    known = store.memories(session_id)

    if not wanted:
        return {"status": "refused", "reason": "name at least one memory"}

    grants = [g for g in store.grants(session_id) if not g.revoked and now < g.expires_at]
    covered = [p for p in wanted if any(g.covers(p, now) for g in grants)]
    missing = [p for p in wanted if p not in covered]

    granted: list[Memory] = []
    if covered:
        ordinary, special = policy.split_by_category(covered, known)
        for group in (ordinary, special):
            if not group:
                continue
            try:
                allowed = policy.validate_request(group, known)
            except PaperTrailError:
                continue
            granted.extend(store.read(session_id, allowed, dict.fromkeys(allowed, purpose), now))
        for grant in grants:
            if any(grant.covers(m.path, now) for m in granted):
                store.note_grant_read(grant.id)

    result: dict[str, Any] = {
        "status": "ok" if granted and not missing else ("partial" if granted else "pending"),
        "context": policy.project(granted),
        "stamped": [m.path for m in granted],
    }

    if missing:
        request_id = store.open_request(session_id, app, missing, purpose, now)
        result["pending"] = {
            "id": request_id,
            "paths": missing,
            "reason": "the holder has not granted these yet",
        }
    return result


def propose_memory(
    store: Store, session_id: str, app: str, path: str, value: str, note: str
) -> dict[str, Any]:
    """Offer a memory. It is never written here; the holder decides."""
    from papertrail.llm import SAFE_PATH

    clean = path.strip().lower()
    if not SAFE_PATH.match(clean) or clean in store.memories(session_id) or not value.strip():
        return {"status": "refused", "reason": "not a well-formed new memory"}

    store.stamp(
        session_id,
        ReceiptAction.SUGGESTED,
        clean,
        f"proposed by {app}",
        value.strip()[:120],
        time.time(),
    )
    store.open_request(session_id, app, [clean], f"remember: {value.strip()[:80]}", time.time())
    return {"status": "pending", "reason": "waiting for the holder to accept it"}


def approve(
    store: Store, session_id: str, request_id: str, paths: list[str], standing: bool
) -> bool:
    """Settle a pending request, optionally leaving a standing grant behind."""
    now = time.time()
    settled = store.settle_request(session_id, request_id)
    if settled is None:
        return False
    allowed = [p for p in paths if p in settled.paths]
    if allowed:
        store.grant(session_id, settled.app, allowed, GRANT_TTL if standing else 60.0, now)
    else:
        store.stamp(
            session_id,
            ReceiptAction.REFUSED,
            ", ".join(settled.paths),
            "refused by the holder",
            f"{settled.app} was turned down",
            now,
        )
    return True
