"""HTTP surface. Holds no rules: it routes, and asks the modules that decide."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from papertrail import export, extract, llm, mcp, policy, turn
from papertrail.models import Memory, MemorySource, PaperTrailError, ReceiptAction, Stamp
from papertrail.seed import HOLDER, STARTERS
from papertrail.store import Store, database_path

COOKIE = "pt_sid"
# The built React app: env var wins; else repo-relative web/dist; else the
# vanilla-JS fallback template that ships with the package.
_ENV_DIST = os.environ.get("PAPERTRAIL_WEB_DIST")
_REPO_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
WEB_DIST = Path(_ENV_DIST) if _ENV_DIST else _REPO_DIST
TEMPLATE = (
    WEB_DIST / "index.html"
    if (WEB_DIST / "index.html").is_file()
    else Path(__file__).parent / "templates" / "index.html"
)

ASKS_PER_SESSION = 14
ASKS_PER_MINUTE = 30

_recent: deque[float] = deque(maxlen=ASKS_PER_MINUTE)

llm.load_key_file()


def _global_limited(now: float) -> bool:
    while _recent and now - _recent[0] > 60:
        _recent.popleft()
    if len(_recent) >= ASKS_PER_MINUTE:
        return True
    _recent.append(now)
    return False


RETENTION = 60 * 60 * 24


async def _purge_loop(store: Store) -> None:
    while True:
        await asyncio.sleep(60 * 30)
        gone = store.purge(RETENTION, time.time())
        if gone:
            logging.getLogger("papertrail").info("purged %d stale sessions", gone)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    store = Store(database_path())
    store.purge(RETENTION, time.time())
    app.state.store = store
    app.state.client = llm.Client() if llm.configured() else None
    keeper = asyncio.create_task(_purge_loop(store))
    yield
    keeper.cancel()
    if app.state.client is not None:
        await app.state.client.aclose()


app = FastAPI(title="Paper Trail", lifespan=lifespan)

if (WEB_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


async def _body(request: Request) -> dict[str, Any]:
    """The posted JSON, or an empty mapping."""
    try:
        payload = await request.json()
    except (ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _session(request: Request) -> str:
    """This visitor's own memory file, minted on first sight."""
    session_id = request.cookies.get(COOKIE) or uuid.uuid4().hex
    store: Store = request.app.state.store
    store.open_session(session_id, time.time())
    return session_id


def _reply(data: dict[str, Any], session_id: str) -> JSONResponse:
    """Answer, and carry the session cookie back with it."""
    response = JSONResponse(data)
    response.set_cookie(COOKIE, session_id, max_age=60 * 60 * 24, httponly=True, samesite="lax")
    return response


def _state(store: Store, session_id: str, client: llm.Client | None) -> dict[str, Any]:
    memories = store.memories(session_id)
    borrowed = any(m.source == "seeded" for m in memories.values())
    return {
        "holder": HOLDER if borrowed else "",
        "starters": list(STARTERS),
        "live": client is not None,
        "model": client.model if client else "cached demo responses",
        "memories": [
            {
                "path": m.path,
                "note": m.note,
                "value": m.value,
                "attested": m.attested,
                "sensitive": m.sensitive,
                "revoked": m.revoked,
                "source": m.source,
            }
            for m in memories.values()
        ],
        "receipts": [r.as_dict() for r in store.receipts(session_id)],
        "shares": [s.as_dict() for s in store.shares(session_id)],
        "grants": [g.as_dict() for g in store.grants(session_id)],
        "pending": [p.as_dict() for p in store.pending(session_id)],
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    session_id = _session(request)
    response = HTMLResponse(TEMPLATE.read_text(encoding="utf-8"))
    response.set_cookie(COOKIE, session_id, max_age=60 * 60 * 24, httponly=True, samesite="lax")
    return response


@app.get("/api/state")
async def state(request: Request) -> JSONResponse:
    session_id = _session(request)
    return _reply(_state(request.app.state.store, session_id, request.app.state.client), session_id)


def _too_busy(store: Store, session_id: str) -> str:
    """The reason to turn a question away, or empty if there isn't one."""
    if _global_limited(time.time()):
        return "This desk is busy right now. Give it a minute and ask again."
    if store.count_ask(session_id) > ASKS_PER_SESSION:
        return "That is the limit for one visit. Reset the memory file to keep going."
    return ""


@app.post("/api/ask")
async def ask(request: Request) -> JSONResponse:
    """What the model wants. In ask-first mode that is all this does."""
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    question = str(body.get("question") or "").strip()[:400]

    if not question:
        return JSONResponse({"error": "ask something first"}, status_code=400)
    if notice := _too_busy(store, session_id):
        return _reply(
            {"notice": notice, **_state(store, session_id, request.app.state.client)}, session_id
        )

    if str(body.get("mode") or "") == "ask":
        proposal = await turn.propose(store, session_id, question, request.app.state.client)
        return _reply(
            {
                "proposal": proposal.as_dict(),
                **_state(store, session_id, request.app.state.client),
            },
            session_id,
        )

    result = await turn.run(store, session_id, question, request.app.state.client)
    return _reply(
        {**result.as_dict(), **_state(store, session_id, request.app.state.client)}, session_id
    )


@app.post("/api/answer")
async def answer(request: Request) -> JSONResponse:
    """Hand over what the holder ticked, and answer from exactly that.

    The browser sends back the paths it was offered, so this endpoint trusts it with
    nothing: policy still refuses anything unknown or revoked.
    """
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    question = str(body.get("question") or "").strip()[:400]
    granted = [str(p) for p in body.get("granted") or []][:32]
    purposes = {
        str(k): str(v)[:80] for k, v in (body.get("purposes") or {}).items() if isinstance(k, str)
    }
    denied = [str(p) for p in body.get("denied") or []][:32]

    if not question:
        return JSONResponse({"error": "ask something first"}, status_code=400)
    if notice := _too_busy(store, session_id):
        return _reply(
            {"notice": notice, **_state(store, session_id, request.app.state.client)}, session_id
        )

    known = store.memories(session_id)
    now = time.time()
    refused = [
        Stamp(
            path=path,
            note=known[path].note,
            purpose=purposes.get(path, ""),
            kind="refused",
            reason="refused by the holder",
        )
        for path in denied
        if path in known
    ]
    for stamp in refused:
        store.stamp(session_id, ReceiptAction.REFUSED, stamp.path, stamp.purpose, stamp.reason, now)

    result = await turn.answer(
        store,
        session_id,
        question,
        granted,
        purposes,
        request.app.state.client,
        refused=refused,
    )
    return _reply(
        {**result.as_dict(), **_state(store, session_id, request.app.state.client)}, session_id
    )


@app.post("/api/demo")
async def demo(request: Request) -> JSONResponse:
    """Fill an empty file with the demo persona."""
    session_id = _session(request)
    store: Store = request.app.state.store
    store.seed(session_id, time.time())
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.post("/api/import")
async def import_text(request: Request) -> JSONResponse:
    """Candidate memories from pasted text. Nothing is written until the holder ticks."""
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    text = str(body.get("text") or "").strip()[: extract.MAX_INPUT]

    if len(text) < 20:
        return JSONResponse({"error": "paste a little more than that"}, status_code=400)
    if notice := _too_busy(store, session_id):
        return _reply(
            {"notice": notice, **_state(store, session_id, request.app.state.client)}, session_id
        )

    taken = list(store.memories(session_id))
    client: llm.Client | None = request.app.state.client
    candidates: list[Memory] = []
    if client is not None:
        try:
            candidates = await extract.extract(client, text, taken)
        except (httpx.HTTPError, KeyError, ValueError):
            candidates = []
    if not candidates:
        candidates = extract.fallback(text, taken)

    store.stamp(
        session_id,
        ReceiptAction.IMPORTED,
        "-",
        "read text the holder pasted",
        f"{len(candidates)} candidates from {len(text)} characters",
        time.time(),
    )
    return _reply(
        {
            "candidates": [
                {
                    "path": m.path,
                    "value": m.value,
                    "note": m.note,
                    "attested": m.attested,
                    "sensitive": m.sensitive,
                }
                for m in candidates
            ],
            **_state(store, session_id, request.app.state.client),
        },
        session_id,
    )


@app.post("/api/keep")
async def keep(request: Request) -> JSONResponse:
    """Write the candidates the holder ticked, and stamp the ones they left behind."""
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    now = time.time()
    taken = set(store.memories(session_id))

    kept = 0
    for item in (body.get("keep") or [])[: extract.MAX_CANDIDATES]:
        if not isinstance(item, dict):
            continue
        memory = _candidate(item, taken)
        if memory is None:
            continue
        if store.remember(session_id, memory, now):
            taken.add(memory.path)
            kept += 1

    for item in (body.get("drop") or [])[: extract.MAX_CANDIDATES]:
        if isinstance(item, dict):
            store.stamp(
                session_id,
                ReceiptAction.DECLINED,
                str(item.get("path") or "")[:64],
                "not kept by the holder",
                str(item.get("value") or "")[:120],
                now,
            )

    return _reply({"kept": kept, **_state(store, session_id, request.app.state.client)}, session_id)


def _candidate(item: dict[str, Any], taken: set[str]) -> Memory | None:
    """A candidate the browser sent back, re-checked rather than believed."""
    path = str(item.get("path") or "").strip().lower()
    value = str(item.get("value") or "").strip()
    note = str(item.get("note") or "").strip()
    if not llm.SAFE_PATH.match(path) or path in taken or not value or not note:
        return None
    return Memory(
        path=path,
        value=value[:400],
        note=note[:80],
        attested=bool(item.get("attested")),
        sensitive=bool(item.get("sensitive")),
        source=str(MemorySource.IMPORTED),
    )


SHARE_TTL = 60 * 60


@app.post("/api/agent")
async def agent(request: Request) -> JSONResponse:
    """The token an assistant elsewhere mounts this file with."""
    session_id = _session(request)
    store: Store = request.app.state.store
    token = store.agent_token(session_id, time.time())
    return _reply(
        {"token": token, **_state(store, session_id, request.app.state.client)}, session_id
    )


KNOCK_APP = "Claude Desktop"
KNOCK_PURPOSE = "answering a question in another chat"


@app.post("/api/knock")
async def knock(request: Request) -> JSONResponse:
    """Have an assistant elsewhere ask for something, so the holder can watch it happen.

    The same call an MCP client makes, against this visitor's own file: it opens a real
    pending request, and nothing is handed over until the holder settles it.
    """
    session_id = _session(request)
    store: Store = request.app.state.store
    wanted = [m.path for m in store.live(session_id) if not m.sensitive][:3]
    state = _state(store, session_id, request.app.state.client)
    if not wanted:
        return _reply({"notice": "Nothing in the file to ask for yet.", **state}, session_id)
    mcp.request_context(store, session_id, KNOCK_APP, wanted, KNOCK_PURPOSE)
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.post("/api/settle")
async def settle(request: Request) -> JSONResponse:
    """Answer a request an assistant is waiting on."""
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    mcp.approve(
        store,
        session_id,
        str(body.get("id") or "")[:64],
        [str(p) for p in body.get("paths") or []][:32],
        bool(body.get("standing")),
    )
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.post("/api/ungrant")
async def ungrant(request: Request) -> JSONResponse:
    session_id = _session(request)
    store: Store = request.app.state.store
    grant_id = str((await _body(request)).get("id") or "")[:64]
    store.revoke_grant(session_id, grant_id, time.time())
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.post("/mcp/{token}/{tool}")
async def mcp_tool(token: str, tool: str, request: Request) -> JSONResponse:
    """The agent-facing surface. The token names a file; the holder still decides."""
    store: Store = request.app.state.store
    session_id = store.session_for_agent(token[:64])
    if session_id is None:
        return JSONResponse({"error": "unknown agent token"}, status_code=404)

    body = await _body(request)
    app_name = str(body.get("app") or "an assistant")[:40]

    if tool == "list_context":
        return JSONResponse(mcp.describe(store, session_id))
    if tool == "request_context":
        return JSONResponse(
            mcp.request_context(
                store,
                session_id,
                app_name,
                [str(p) for p in body.get("paths") or []],
                str(body.get("purpose") or "")[:120],
            )
        )
    if tool == "propose_memory":
        return JSONResponse(
            mcp.propose_memory(
                store,
                session_id,
                app_name,
                str(body.get("path") or ""),
                str(body.get("value") or ""),
                str(body.get("note") or ""),
            )
        )
    return JSONResponse({"error": f"no such tool: {tool}"}, status_code=404)


@app.post("/api/share")
async def share(request: Request) -> JSONResponse:
    """Mint a read-only link over a subset of the file."""
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    wanted = [str(p) for p in body.get("paths") or []][:32]
    try:
        paths = policy.authorize_share(wanted, store.memories(session_id))
    except PaperTrailError as refusal:
        return JSONResponse(refusal.as_dict(), status_code=400)
    token = store.create_share(session_id, paths, SHARE_TTL, time.time())
    return _reply(
        {"token": token, **_state(store, session_id, request.app.state.client)}, session_id
    )


@app.post("/api/unshare")
async def unshare(request: Request) -> JSONResponse:
    session_id = _session(request)
    store: Store = request.app.state.store
    token = str((await _body(request)).get("token") or "")[:64]
    store.revoke_share(session_id, token, time.time())
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.get("/api/shared/{token}")
async def shared(token: str, request: Request) -> JSONResponse:
    """What a link carries. Opening it is stamped in the holder's ledger."""
    store: Store = request.app.state.store
    opened = store.open_share(token[:64], time.time())
    if opened is None:
        return JSONResponse({"error": "this link has expired or been revoked"}, status_code=404)
    _, memories = opened
    return JSONResponse(
        {
            "memories": [
                {
                    "path": m.path,
                    "note": m.note,
                    "value": "" if m.attested else m.value,
                    "attested": m.attested,
                    "source": m.source,
                }
                for m in memories
            ]
        }
    )


@app.get("/api/export")
async def export_file(request: Request) -> Response:
    """The whole memory file and its ledger, as JSON or Markdown."""
    session_id = _session(request)
    store: Store = request.app.state.store
    memories = list(store.memories(session_id).values())
    receipts = store.receipts(session_id, limit=1000)
    store.stamp(
        session_id,
        ReceiptAction.EXPORTED,
        "-",
        "exported by the holder",
        f"{len(memories)} memories, {len(receipts)} ledger lines",
        time.time(),
    )
    if request.query_params.get("format") == "markdown":
        return PlainTextResponse(
            export.as_markdown(memories, receipts, HOLDER),
            headers={"Content-Disposition": 'attachment; filename="memory-file.md"'},
        )
    return JSONResponse(
        export.as_json(memories, receipts, HOLDER),
        headers={"Content-Disposition": 'attachment; filename="memory-file.json"'},
    )


@app.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    store: Store = request.app.state.store
    try:
        with store._connect() as con:
            con.execute("SELECT 1").fetchone()
        db_ok = True
    except sqlite3.Error:
        db_ok = False
    payload = {"ok": db_ok, "model": bool(request.app.state.client), "db": db_ok}
    return JSONResponse(payload, status_code=200 if db_ok else 503)


@app.post("/api/remember")
async def remember(request: Request) -> JSONResponse:
    """Keep a memory the assistant proposed and the holder accepted."""
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    kept = llm.parse_suggestion(json.dumps({"remember": body}), list(store.memories(session_id)))
    if kept is None:
        return JSONResponse({"error": "not a memory this file can take"}, status_code=400)
    store.remember(
        session_id, Memory(path=kept.path, value=kept.value, note=kept.note), time.time()
    )
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.post("/api/decline")
async def decline(request: Request) -> JSONResponse:
    """Turn a proposal down, and stamp that too."""
    session_id = _session(request)
    store: Store = request.app.state.store
    body = await _body(request)
    path = str(body.get("path") or "")[:64]
    store.stamp(
        session_id,
        ReceiptAction.DECLINED,
        path,
        "turned down by the holder",
        str(body.get("value") or "")[:120],
        time.time(),
    )
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.post("/api/stream")
async def stream(request: Request) -> Response:
    """One turn as server-sent events: stamps first, then the answer as it arrives."""
    session_id = _session(request)
    store: Store = request.app.state.store
    client = request.app.state.client
    body = await _body(request)
    question = str(body.get("question") or "").strip()[:400]

    if not question:
        return JSONResponse({"error": "ask something first"}, status_code=400)
    if notice := _too_busy(store, session_id):
        return _reply({"notice": notice, **_state(store, session_id, client)}, session_id)

    granted: list[str] | None = None
    refused: list[Stamp] = []
    purposes: dict[str, str] = {}
    if isinstance(body.get("granted"), list):
        granted = [str(p) for p in body["granted"]][:32]
        purposes = {
            str(k): str(v)[:80]
            for k, v in (body.get("purposes") or {}).items()
            if isinstance(k, str)
        }
        known = store.memories(session_id)
        now = time.time()
        refused = [
            Stamp(
                path=path,
                note=known[path].note,
                purpose=purposes.get(path, ""),
                kind="refused",
                reason="refused by the holder",
            )
            for path in [str(p) for p in body.get("denied") or []][:32]
            if path in known
        ]
        for stamp in refused:
            store.stamp(
                session_id, ReceiptAction.REFUSED, stamp.path, stamp.purpose, stamp.reason, now
            )

    async def events() -> AsyncIterator[bytes]:
        try:
            async for name, payload in turn.stream(
                store, session_id, question, client, granted, purposes, refused
            ):
                yield f"event: {name}\ndata: {json.dumps(payload)}\n\n".encode()
        except Exception:
            yield b'event: error\ndata: {"message": "that did not go through"}\n\n'
        yield f"event: state\ndata: {json.dumps(_state(store, session_id, client))}\n\n".encode()

    response = StreamingResponse(events(), media_type="text/event-stream")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Accel-Buffering"] = "no"
    response.set_cookie(COOKIE, session_id, max_age=60 * 60 * 24, httponly=True, samesite="lax")
    return response


@app.post("/api/revoke")
async def revoke(request: Request) -> JSONResponse:
    session_id = _session(request)
    store: Store = request.app.state.store
    path = str((await _body(request)).get("path") or "").strip()
    store.revoke(session_id, path, time.time())
    return _reply(_state(store, session_id, request.app.state.client), session_id)


@app.post("/api/restore")
async def restore(request: Request) -> JSONResponse:
    session_id = _session(request)
    store: Store = request.app.state.store
    store.restore(session_id, time.time())
    return _reply(_state(store, session_id, request.app.state.client), session_id)


def main() -> None:
    """Serve on loopback; the reverse proxy in front terminates TLS."""
    import uvicorn

    # LLM calls emit one JSON line per call on `papertrail.llm`; make sure it
    # reaches the same stream uvicorn writes to.
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("papertrail").setLevel(logging.INFO)

    uvicorn.run(
        app,
        host=os.environ.get("PAPERTRAIL_HOST", "127.0.0.1"),
        port=int(os.environ.get("PAPERTRAIL_PORT", "8790")),
        log_level="info",
    )
