"""The SQLite repository: the only module that touches a database.

Every read and every write records its receipt inside the same transaction as the effect,
so a memory that reached a model without a ledger line is unreachable rather than unlikely.
Rows are keyed by session, so one visitor cannot change what another sees.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from papertrail.models import (
    Grant,
    Memory,
    MemorySource,
    PendingRequest,
    Receipt,
    ReceiptAction,
    Share,
)
from papertrail.seed import SEED

DB_ENV = "PAPERTRAIL_DB"
DEFAULT_DB = "papertrail.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,
  created_at REAL NOT NULL,
  asks       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS memories (
  session_id TEXT NOT NULL REFERENCES sessions(id),
  path       TEXT NOT NULL,
  value      TEXT NOT NULL,
  note       TEXT NOT NULL,
  attested   INTEGER NOT NULL DEFAULT 0,
  sensitive  INTEGER NOT NULL DEFAULT 0,
  revoked    INTEGER NOT NULL DEFAULT 0,
  ordinal    INTEGER NOT NULL,
  source     TEXT NOT NULL DEFAULT 'seeded',
  created_at REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (session_id, path)
);
CREATE TABLE IF NOT EXISTS receipts (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  action     TEXT NOT NULL,
  path       TEXT NOT NULL,
  purpose    TEXT NOT NULL,
  detail     TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shares (
  token      TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  paths      TEXT NOT NULL,
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL,
  views      INTEGER NOT NULL DEFAULT 0,
  revoked    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS grants (
  id         TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  app        TEXT NOT NULL,
  paths      TEXT NOT NULL,
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL,
  reads      INTEGER NOT NULL DEFAULT 0,
  revoked    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS agents (
  token      TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pending (
  id         TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  app        TEXT NOT NULL,
  paths      TEXT NOT NULL,
  purpose    TEXT NOT NULL,
  created_at REAL NOT NULL,
  settled    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS grants_by_session ON grants(session_id);
CREATE INDEX IF NOT EXISTS pending_by_session ON pending(session_id);
CREATE INDEX IF NOT EXISTS receipts_by_session ON receipts(session_id, id DESC);
CREATE INDEX IF NOT EXISTS shares_by_session ON shares(session_id);
"""


def database_path() -> Path:
    return Path(os.environ.get(DB_ENV, DEFAULT_DB))


MIGRATIONS_DIR = Path(os.environ.get("PAPERTRAIL_MIGRATIONS", "migrations"))


def _migrate(con: sqlite3.Connection, dir: Path) -> None:
    """Run numbered SQL files from ``dir`` once each, in order.

    Idempotent. Column-additive migrations (ALTER TABLE ADD COLUMN) are
    silently skipped when the column already exists, so a box that ran an
    older code path still catches up cleanly.
    """
    con.execute("CREATE TABLE IF NOT EXISTS _migrations (id INTEGER PRIMARY KEY, applied REAL)")
    done = {row[0] for row in con.execute("SELECT id FROM _migrations")}
    if not dir.is_dir():
        return
    for path in sorted(dir.glob("[0-9][0-9][0-9]_*.sql")):
        n = int(path.name[:3])
        if n in done:
            continue
        try:
            con.executescript(path.read_text())
        except sqlite3.OperationalError as exc:
            # ALTER TABLE ADD COLUMN when the column already exists → skip.
            if "duplicate column name" not in str(exc):
                raise
        con.execute("INSERT INTO _migrations(id, applied) VALUES (?, ?)", (n, time.time()))
        con.commit()


class Store:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if self.path.parent != Path(""):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(SCHEMA)
            _migrate(con, MIGRATIONS_DIR)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def open_session(self, session_id: str, now: float) -> None:
        """Register a visitor. Their memory file starts empty until they choose one."""
        with self._connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO sessions(id, created_at) VALUES (?, ?)", (session_id, now)
            )

    def seed(self, session_id: str, now: float) -> bool:
        """Fill an empty file with the demo persona. False if it already holds anything."""
        with self._connect() as con:
            if con.execute(
                "SELECT 1 FROM memories WHERE session_id = ? LIMIT 1", (session_id,)
            ).fetchone():
                return False
            con.executemany(
                "INSERT INTO memories(session_id, path, value, note, attested, sensitive,"
                " revoked, ordinal, source, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                [
                    (
                        session_id,
                        m.path,
                        m.value,
                        m.note,
                        int(m.attested),
                        int(m.sensitive),
                        i,
                        str(MemorySource.SEEDED),
                        now,
                    )
                    for i, m in enumerate(SEED)
                ],
            )
        return True

    def memories(self, session_id: str) -> dict[str, Memory]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM memories WHERE session_id = ? ORDER BY ordinal", (session_id,)
            ).fetchall()
        return {row["path"]: _memory(row) for row in rows}

    def live(self, session_id: str) -> list[Memory]:
        return [m for m in self.memories(session_id).values() if not m.revoked]

    def read(
        self, session_id: str, paths: Sequence[str], purposes: dict[str, str], now: float
    ) -> list[Memory]:
        """Hand over these memories and stamp the ledger, both or neither."""
        if not paths:
            return []
        with self._connect() as con:
            marks = ",".join("?" for _ in paths)
            rows = con.execute(
                f"SELECT * FROM memories WHERE session_id = ? AND path IN ({marks})"
                " AND revoked = 0 ORDER BY ordinal",
                (session_id, *paths),
            ).fetchall()
            found = [_memory(row) for row in rows]
            con.executemany(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        session_id,
                        str(ReceiptAction.SENSITIVE_READ if m.sensitive else ReceiptAction.READ),
                        m.path,
                        purposes.get(m.path, ""),
                        "proof of existence only" if m.attested else "value handed over",
                        now,
                    )
                    for m in found
                ],
            )
        return found

    def stamp(
        self,
        session_id: str,
        action: ReceiptAction,
        path: str,
        purpose: str,
        detail: str,
        now: float,
    ) -> None:
        with self._connect() as con:
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, str(action), path, purpose, detail, now),
            )

    def remember(self, session_id: str, memory: Memory, now: float) -> bool:
        """Append a memory the holder accepted. False if the path is already taken."""
        with self._connect() as con:
            taken = con.execute(
                "SELECT 1 FROM memories WHERE session_id = ? AND path = ?",
                (session_id, memory.path),
            ).fetchone()
            if taken:
                return False
            ordinal = con.execute(
                "SELECT COALESCE(MAX(ordinal), -1) + 1 FROM memories WHERE session_id = ?",
                (session_id,),
            ).fetchone()[0]
            con.execute(
                "INSERT INTO memories(session_id, path, value, note, attested, sensitive,"
                " revoked, ordinal, source, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                (
                    session_id,
                    memory.path,
                    memory.value,
                    memory.note,
                    int(memory.attested),
                    int(memory.sensitive),
                    ordinal,
                    memory.source,
                    now,
                ),
            )
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    str(ReceiptAction.REMEMBERED),
                    memory.path,
                    "kept by the holder",
                    memory.value[:120],
                    now,
                ),
            )
        return True

    def revoke(self, session_id: str, path: str, now: float) -> bool:
        """Tombstone a memory and stamp it. False if it was already gone."""
        with self._connect() as con:
            changed = con.execute(
                "UPDATE memories SET revoked = 1 WHERE session_id = ? AND path = ? AND revoked = 0",
                (session_id, path),
            ).rowcount
            if not changed:
                return False
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    str(ReceiptAction.REVOKED),
                    path,
                    "revoked by the holder",
                    "never offered to the model again",
                    now,
                ),
            )
        return True

    def restore(self, session_id: str, now: float) -> None:
        """Empty the file and its ledger so the visitor can start over."""
        with self._connect() as con:
            con.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
            con.execute("DELETE FROM receipts WHERE session_id = ?", (session_id,))
            con.execute("UPDATE sessions SET asks = 0 WHERE id = ?", (session_id,))

    def create_share(self, session_id: str, paths: Sequence[str], ttl: float, now: float) -> str:
        """Mint a read-only token over a subset, and stamp that it was minted."""
        token = secrets.token_urlsafe(9)
        with self._connect() as con:
            con.execute(
                "INSERT INTO shares(token, session_id, paths, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (token, session_id, json.dumps(list(paths)), now, now + ttl),
            )
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    str(ReceiptAction.SHARED),
                    ", ".join(paths),
                    "link created by the holder",
                    f"expires in {int(ttl / 60)} minutes",
                    now,
                ),
            )
        return token

    def open_share(self, token: str, now: float) -> tuple[str, list[Memory]] | None:
        """The memories a live token covers, stamping the holder's ledger with the view."""
        with self._connect() as con:
            row = con.execute("SELECT * FROM shares WHERE token = ?", (token,)).fetchone()
            if row is None or row["revoked"] or row["expires_at"] <= now:
                return None
            paths = list(json.loads(row["paths"]))
            if not paths:
                return row["session_id"], []
            marks = ",".join("?" for _ in paths)
            found = [
                _memory(item)
                for item in con.execute(
                    f"SELECT * FROM memories WHERE session_id = ? AND path IN ({marks})"
                    " AND revoked = 0 ORDER BY ordinal",
                    (row["session_id"], *paths),
                ).fetchall()
            ]
            con.execute("UPDATE shares SET views = views + 1 WHERE token = ?", (token,))
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["session_id"],
                    str(ReceiptAction.VIEWED),
                    ", ".join(m.path for m in found),
                    "someone opened the link",
                    f"view {row['views'] + 1}",
                    now,
                ),
            )
        return row["session_id"], found

    def shares(self, session_id: str) -> list[Share]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM shares WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return [
            Share(
                token=row["token"],
                paths=tuple(json.loads(row["paths"])),
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                views=row["views"],
                revoked=bool(row["revoked"]),
            )
            for row in rows
        ]

    def revoke_share(self, session_id: str, token: str, now: float) -> bool:
        with self._connect() as con:
            changed = con.execute(
                "UPDATE shares SET revoked = 1 WHERE token = ? AND session_id = ? AND revoked = 0",
                (token, session_id),
            ).rowcount
            if not changed:
                return False
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    str(ReceiptAction.UNSHARED),
                    token,
                    "link revoked by the holder",
                    "it returns nothing from now on",
                    now,
                ),
            )
        return True

    def agent_token(self, session_id: str, now: float) -> str:
        """The token an agent mounts this file with. One per file, stable once minted."""
        with self._connect() as con:
            row = con.execute(
                "SELECT token FROM agents WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                return str(row["token"])
            token = secrets.token_urlsafe(12)
            con.execute(
                "INSERT INTO agents(token, session_id, created_at) VALUES (?, ?, ?)",
                (token, session_id, now),
            )
        return token

    def session_for_agent(self, token: str) -> str | None:
        with self._connect() as con:
            row = con.execute("SELECT session_id FROM agents WHERE token = ?", (token,)).fetchone()
        return str(row["session_id"]) if row else None

    def open_request(
        self, session_id: str, app: str, paths: Sequence[str], purpose: str, now: float
    ) -> str:
        request_id = secrets.token_urlsafe(6)
        with self._connect() as con:
            con.execute(
                "INSERT INTO pending(id, session_id, app, paths, purpose, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (request_id, session_id, app, json.dumps(list(paths)), purpose, now),
            )
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    str(ReceiptAction.REQUESTED),
                    ", ".join(paths),
                    purpose[:80],
                    f"{app} is waiting on an answer",
                    now,
                ),
            )
        return request_id

    def pending(self, session_id: str) -> list[PendingRequest]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM pending WHERE session_id = ? AND settled = 0"
                " ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return [_pending(row) for row in rows]

    def settle_request(self, session_id: str, request_id: str) -> PendingRequest | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM pending WHERE id = ? AND session_id = ? AND settled = 0",
                (request_id, session_id),
            ).fetchone()
            if row is None:
                return None
            con.execute("UPDATE pending SET settled = 1 WHERE id = ?", (request_id,))
        return _pending(row)

    def grant(self, session_id: str, app: str, paths: Sequence[str], ttl: float, now: float) -> str:
        grant_id = secrets.token_urlsafe(6)
        with self._connect() as con:
            con.execute(
                "INSERT INTO grants(id, session_id, app, paths, created_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (grant_id, session_id, app, json.dumps(list(paths)), now, now + ttl),
            )
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    str(ReceiptAction.GRANTED),
                    ", ".join(paths),
                    f"standing grant to {app}",
                    f"good for {int(ttl / 60)} minutes unless revoked",
                    now,
                ),
            )
        return grant_id

    def grants(self, session_id: str) -> list[Grant]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM grants WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return [
            Grant(
                id=row["id"],
                app=row["app"],
                paths=tuple(json.loads(row["paths"])),
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                reads=row["reads"],
                revoked=bool(row["revoked"]),
            )
            for row in rows
        ]

    def revoke_grant(self, session_id: str, grant_id: str, now: float) -> bool:
        with self._connect() as con:
            changed = con.execute(
                "UPDATE grants SET revoked = 1 WHERE id = ? AND session_id = ? AND revoked = 0",
                (grant_id, session_id),
            ).rowcount
            if not changed:
                return False
            con.execute(
                "INSERT INTO receipts(session_id, action, path, purpose, detail, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    str(ReceiptAction.REVOKED),
                    grant_id,
                    "standing grant revoked by the holder",
                    "the agent is asked again from now on",
                    now,
                ),
            )
        return True

    def note_grant_read(self, grant_id: str) -> None:
        with self._connect() as con:
            con.execute("UPDATE grants SET reads = reads + 1 WHERE id = ?", (grant_id,))

    def purge(self, older_than: float, now: float) -> int:
        """Delete sessions untouched for `older_than` seconds, and everything they hold.

        Visitors paste personal text into this and there are no accounts, so the only
        honest retention policy is a short one.
        """
        cutoff = now - older_than
        with self._connect() as con:
            stale = [
                row["id"]
                for row in con.execute(
                    "SELECT id FROM sessions WHERE created_at < ?", (cutoff,)
                ).fetchall()
            ]
            if not stale:
                return 0
            marks = ",".join("?" for _ in stale)
            for table in ("grants", "pending", "agents", "shares", "memories"):
                con.execute(f"DELETE FROM {table} WHERE session_id IN ({marks})", stale)
            con.execute(f"DELETE FROM receipts WHERE session_id IN ({marks})", stale)
            con.execute(f"DELETE FROM sessions WHERE id IN ({marks})", stale)
        return len(stale)

    def receipts(self, session_id: str, limit: int = 200) -> list[Receipt]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM receipts WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            Receipt(
                action=ReceiptAction(row["action"]),
                path=row["path"],
                purpose=row["purpose"],
                detail=row["detail"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def count_ask(self, session_id: str) -> int:
        """Record one question and return how many this session has asked."""
        with self._connect() as con:
            con.execute("UPDATE sessions SET asks = asks + 1 WHERE id = ?", (session_id,))
            row = con.execute("SELECT asks FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return int(row["asks"]) if row else 0


def _pending(row: sqlite3.Row) -> PendingRequest:
    return PendingRequest(
        id=row["id"],
        app=row["app"],
        paths=tuple(json.loads(row["paths"])),
        purpose=row["purpose"],
        created_at=row["created_at"],
    )


def _memory(row: sqlite3.Row) -> Memory:
    return Memory(
        path=row["path"],
        value=row["value"],
        note=row["note"],
        attested=bool(row["attested"]),
        sensitive=bool(row["sensitive"]),
        revoked=bool(row["revoked"]),
        source=row["source"],
        created_at=row["created_at"],
    )
