from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    EMPTY_REQUEST = "EMPTY_REQUEST"
    UNKNOWN_FIELDS = "UNKNOWN_FIELDS"
    MIXED_SENSITIVE = "MIXED_SENSITIVE"
    REVOKED = "REVOKED"


class MemorySource(StrEnum):
    SEEDED = "seeded"
    IMPORTED = "imported"
    PROPOSED = "proposed"


class ReceiptAction(StrEnum):
    READ = "read"
    SENSITIVE_READ = "sensitive_read"
    REFUSED = "refused"
    REVOKED = "revoked"
    ASKED = "asked"
    SUGGESTED = "suggested"
    REMEMBERED = "remembered"
    DECLINED = "declined"
    IMPORTED = "imported"
    EXPORTED = "exported"
    SHARED = "shared"
    VIEWED = "viewed"
    UNSHARED = "unshared"
    REQUESTED = "requested"
    GRANTED = "granted"


class PaperTrailError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"code": str(self.code), "message": self.message}


@dataclass(frozen=True, slots=True)
class Memory:
    """A remembered fact.

    `note` is the only part ever shown to the scoping model: it says what the memory is
    about without saying what it holds. `attested` means the value never leaves this
    process. `sensitive` marks a special category, which never rides along with ordinary
    fields.
    """

    path: str
    value: str
    note: str
    attested: bool = False
    sensitive: bool = False
    revoked: bool = False
    source: str = "seeded"
    created_at: float = 0.0


@dataclass(frozen=True, slots=True)
class Receipt:
    action: ReceiptAction
    path: str
    purpose: str
    detail: str
    created_at: float

    def as_dict(self) -> dict[str, object]:
        return {
            "action": str(self.action),
            "path": self.path,
            "purpose": self.purpose,
            "detail": self.detail,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class Ask:
    path: str
    note: str
    purpose: str
    sensitive: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "note": self.note,
            "purpose": self.purpose,
            "sensitive": self.sensitive,
        }


@dataclass(frozen=True, slots=True)
class Proposal:
    """What the model asked for, before anything has been handed over.

    Split in two because a special category travels as its own request or not at all.
    """

    question: str
    ordinary: tuple[Ask, ...] = ()
    special: tuple[Ask, ...] = ()
    cached: bool = False

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(a.path for a in self.ordinary + self.special)

    @property
    def purposes(self) -> dict[str, str]:
        return {a.path: a.purpose for a in self.ordinary + self.special}

    def as_dict(self) -> dict[str, object]:
        return {
            "question": self.question,
            "ordinary": [a.as_dict() for a in self.ordinary],
            "special": [a.as_dict() for a in self.special],
            "cached": self.cached,
        }


@dataclass(frozen=True, slots=True)
class Suggestion:
    path: str
    value: str
    note: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "value": self.value, "note": self.note}


@dataclass(frozen=True, slots=True)
class Share:
    token: str
    paths: tuple[str, ...]
    created_at: float
    expires_at: float
    views: int
    revoked: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "token": self.token,
            "paths": list(self.paths),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "views": self.views,
            "revoked": self.revoked,
        }


@dataclass(frozen=True, slots=True)
class PendingRequest:
    id: str
    app: str
    paths: tuple[str, ...]
    purpose: str
    created_at: float

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "app": self.app,
            "paths": list(self.paths),
            "purpose": self.purpose,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class Grant:
    """A standing permission, so an agent need not wake the holder on every call."""

    id: str
    app: str
    paths: tuple[str, ...]
    created_at: float
    expires_at: float
    reads: int
    revoked: bool

    def covers(self, path: str, now: float) -> bool:
        return not self.revoked and now < self.expires_at and path in self.paths

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "app": self.app,
            "paths": list(self.paths),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "reads": self.reads,
            "revoked": self.revoked,
        }


@dataclass(frozen=True, slots=True)
class Stamp:
    """One memory under an answer, and how it travelled.

    `kind` is "value" for a memory handed over as-is, "proof" for an attested memory that
    yielded only its existence, and "refused" for one policy turned down.
    """

    path: str
    note: str
    purpose: str
    kind: str
    reason: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "note": self.note,
            "purpose": self.purpose,
            "kind": self.kind,
            "reason": self.reason,
        }
