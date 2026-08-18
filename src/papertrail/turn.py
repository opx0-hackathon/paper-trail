"""One turn, in two halves: what the model asked for, and what it was allowed to have.

Splitting propose from answer is what makes consent possible rather than merely auditable:
between them nothing has been handed over yet and a person can still say no.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

import httpx

from papertrail import policy
from papertrail.llm import Client, Need
from papertrail.models import (
    Ask,
    Memory,
    PaperTrailError,
    Proposal,
    ReceiptAction,
    Stamp,
    Suggestion,
)
from papertrail.store import Store


@dataclass(frozen=True, slots=True)
class TurnResult:
    answer: str
    stamps: list[Stamp] = field(default_factory=list)
    model: str = ""
    cached: bool = False
    suggestion: Suggestion | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "stamps": [s.as_dict() for s in self.stamps],
            "model": self.model,
            "cached": self.cached,
            "suggestion": self.suggestion.as_dict() if self.suggestion else None,
        }


async def propose(store: Store, session_id: str, question: str, client: Client | None) -> Proposal:
    """Ask the model what it needs, and stamp the asking. Nothing is handed over here."""
    now = time.time()
    live = store.live(session_id)
    known = store.memories(session_id)

    cached = client is None
    needs: list[Need]
    if client is None:
        needs = _cached_needs(question, live)
    else:
        try:
            needs = await client.scope(question, policy.labels_for_scope(live))
        except (httpx.HTTPError, KeyError, ValueError):
            cached = True
            needs = _cached_needs(question, live)

    store.stamp(
        session_id,
        ReceiptAction.ASKED,
        "-",
        question[:120],
        f"model asked for {len(needs)} memories" if needs else "model asked for nothing",
        now,
    )

    asks = {
        need.path: Ask(
            path=need.path,
            note=known[need.path].note,
            purpose=need.purpose,
            sensitive=known[need.path].sensitive,
        )
        for need in needs
        if need.path in known and not known[need.path].revoked
    }
    ordinary, special = policy.split_by_category(list(asks), known)
    return Proposal(
        question=question,
        ordinary=tuple(asks[p] for p in ordinary),
        special=tuple(asks[p] for p in special),
        cached=cached,
    )


async def answer(
    store: Store,
    session_id: str,
    question: str,
    granted: Sequence[str],
    purposes: dict[str, str],
    client: Client | None,
    cached: bool = False,
    refused: Sequence[Stamp] = (),
) -> TurnResult:
    """Hand over exactly what was granted, answer from it, and stamp what it cost.

    Ordinary memories and any special category are validated and read as two separate
    requests, so a granted special category is stamped apart in the ledger.
    """
    now = time.time()
    known = store.memories(session_id)
    ordinary, special = policy.split_by_category(granted, known)

    memories: list[Memory] = []
    turned_down = list(refused)
    for group in (ordinary, special):
        if not group:
            continue
        try:
            paths = policy.validate_request(group, known)
        except PaperTrailError as refusal:
            turned_down.extend(
                _refusal_stamps(store, session_id, group, known, purposes, refusal, now)
            )
            continue
        memories.extend(store.read(session_id, paths, purposes, now))

    context = policy.project(memories)

    suggestion: Suggestion | None = None
    if client is None or cached:
        cached = True
        text = _cached_answer(question, context)
    else:
        try:
            text, suggestion = await asyncio.gather(
                client.answer(question, context),
                _suggest(client, question, list(known)),
            )
        except (httpx.HTTPError, KeyError, ValueError):
            cached = True
            text = _cached_answer(question, context)

    if suggestion is not None:
        store.stamp(
            session_id,
            ReceiptAction.SUGGESTED,
            suggestion.path,
            "proposed by the assistant",
            suggestion.value[:120],
            now,
        )

    return TurnResult(
        answer=text,
        stamps=policy.stamps(memories, purposes) + turned_down,
        model="cached demo response" if cached else (client.model if client else ""),
        cached=cached,
        suggestion=suggestion,
    )


async def _suggest(client: Client, question: str, taken: list[str]) -> Suggestion | None:
    """A proposal, or nothing. Never a reason for the answer beside it to fail."""
    try:
        return await client.suggest(question, taken)
    except (httpx.HTTPError, KeyError, ValueError):
        return None


async def stream(
    store: Store,
    session_id: str,
    question: str,
    client: Client | None,
    granted: Sequence[str] | None = None,
    purposes: dict[str, str] | None = None,
    refused: Sequence[Stamp] = (),
) -> AsyncIterator[tuple[str, object]]:
    """One turn as a sequence of events: what it took, then the answer as it arrives.

    Yields ("stamps", list), then ("token", str) repeatedly, then ("done", dict).
    """
    now = time.time()
    known = store.memories(session_id)
    cached = client is None
    reasons = dict(purposes or {})
    turned_down = list(refused)

    if granted is None:
        proposal = await propose(store, session_id, question, client)
        cached = proposal.cached
        reasons = proposal.purposes
        turned_down = _refuse_special(store, session_id, proposal, now)
        allowed = [ask.path for ask in proposal.ordinary if ask.path in known]
    else:
        allowed = list(granted)

    ordinary, special = policy.split_by_category(allowed, known)
    memories: list[Memory] = []
    for group in (ordinary, special):
        if not group:
            continue
        try:
            paths = policy.validate_request(group, known)
        except PaperTrailError as refusal:
            turned_down.extend(
                _refusal_stamps(store, session_id, group, known, reasons, refusal, now)
            )
            continue
        memories.extend(store.read(session_id, paths, reasons, now))

    context = policy.project(memories)
    yield "stamps", [s.as_dict() for s in policy.stamps(memories, reasons) + turned_down]

    text = ""
    if client is not None and not cached:
        try:
            async for piece in client.stream(question, context):
                text += piece
                yield "token", piece
        except (httpx.HTTPError, KeyError, ValueError):
            cached = True
    if cached or not text.strip():
        cached = True
        text = _cached_answer(question, context)
        yield "token", text

    suggestion = None
    if client is not None and not cached:
        suggestion = await _suggest(client, question, list(known))
        if suggestion is not None:
            store.stamp(
                session_id,
                ReceiptAction.SUGGESTED,
                suggestion.path,
                "proposed by the assistant",
                suggestion.value[:120],
                now,
            )

    yield (
        "done",
        {
            "model": "cached demo response" if cached else (client.model if client else ""),
            "cached": cached,
            "suggestion": suggestion.as_dict() if suggestion else None,
        },
    )


def _refuse_special(store: Store, session_id: str, proposal: Proposal, now: float) -> list[Stamp]:
    refused = [
        Stamp(
            path=ask.path,
            note=ask.note,
            purpose=ask.purpose,
            kind="refused",
            reason="a special category needs a request of its own",
        )
        for ask in proposal.special
    ]
    for stamp in refused:
        store.stamp(session_id, ReceiptAction.REFUSED, stamp.path, stamp.purpose, stamp.reason, now)
    return refused


async def run(store: Store, session_id: str, question: str, client: Client | None) -> TurnResult:
    """Propose and grant in one motion: ordinary memories go through, a special category
    does not. What happens when nobody is being asked first."""
    proposal = await propose(store, session_id, question, client)
    now = time.time()
    known = store.memories(session_id)
    refused = _refuse_special(store, session_id, proposal, now)
    granted = [ask.path for ask in proposal.ordinary if ask.path in known]
    return await answer(
        store,
        session_id,
        question,
        granted,
        proposal.purposes,
        client,
        cached=proposal.cached,
        refused=refused,
    )


def _refusal_stamps(
    store: Store,
    session_id: str,
    group: Sequence[str],
    known: dict[str, Memory],
    purposes: dict[str, str],
    refusal: PaperTrailError,
    now: float,
) -> list[Stamp]:
    """Stamp a refusal and give the interface something to show for it."""
    stamps = [
        Stamp(
            path=path,
            note=known[path].note if path in known else "",
            purpose=purposes.get(path, ""),
            kind="refused",
            reason=refusal.message,
        )
        for path in group
    ]
    for stamp in stamps:
        store.stamp(
            session_id, ReceiptAction.REFUSED, stamp.path, stamp.purpose, refusal.message, now
        )
    return stamps


_WITH_KITCHEN = (
    "Microwave khichdi. Rinse half a cup of rice and half a cup of moong dal, cover with "
    "kettle water and a pinch of turmeric, and microwave in bursts until it stops "
    "resisting the spoon. Around ₹30, no stove involved, and one bowl to wash."
)
_WITHOUT_KITCHEN = (
    "Chickpea curry with rice. Soften an onion in the pan first, then the spices, then "
    "the chickpeas and a splash of coconut milk. Twenty-five minutes on the hob and it "
    "reheats well for tomorrow."
)
_NONVEG = (
    "Chicken keema. Brown the onion properly before the mince goes in, that is the whole "
    "recipe. Around ₹140 of ingredients, and it reheats into tomorrow's lunch."
)
_LACTOSE = (
    "Microwave khichdi, and skip the yoghurt on the side that most recipes suggest. "
    "Rice, moong dal, turmeric, kettle water, microwaved in bursts. Around ₹30, no "
    "stove and nothing dairy in it."
)
_SATURDAY = (
    "Cycle to Cubbon Park before the heat, back by noon. Three hours on Rust with "
    "something instrumental on, the ownership chapter rather than another tutorial. "
    "Keep the evening empty."
)
_EVENING = (
    "Labs finish at 6:30, so nothing ambitious. Kettle dinner, then ninety minutes on "
    "Rust with something instrumental on. Stop before it turns into a fourth hour."
)


def _cached_needs(question: str, live: list[Memory]) -> list[Need]:
    """What a model would plausibly ask for, matched on the words of the question."""
    text = question.lower()
    topics = {
        "diet.style": ("cook", "eat", "food", "dinner", "lunch", "meal", "recipe"),
        "kitchen.equipment": ("cook", "recipe", "dinner", "meal"),
        "health.condition": ("cook", "eat", "food", "dinner", "meal"),
        "budget.weekly": ("cook", "buy", "spend", "budget", "weekend", "saturday"),
        "location.city": ("cook", "buy", "weekend", "saturday", "go", "out"),
        "schedule.evenings": ("evening", "tonight", "saturday", "weekend", "plan", "time"),
        "work.stack": ("evening", "saturday", "weekend", "learn", "study", "plan"),
        "style.tone": (),
        "taste.music": ("evening", "saturday", "weekend", "study"),
        "travel.commute": ("saturday", "weekend", "go", "out"),
    }
    paths = {m.path for m in live}
    return [
        Need(path, "matched on the words of the question")
        for path, words in topics.items()
        if path in paths and any(word in text for word in words)
    ]


def _cached_answer(question: str, context: dict[str, object]) -> str:
    """A stand-in used when the upstream is unreachable, reflecting what was handed over."""
    text = question.lower()
    if any(word in text for word in ("cook", "eat", "food", "dinner", "meal", "recipe")):
        if "diet.style" not in context:
            return _NONVEG
        if "kitchen.equipment" not in context:
            return _WITHOUT_KITCHEN
        return _LACTOSE if "health.condition" in context else _WITH_KITCHEN
    if any(word in text for word in ("saturday", "weekend")):
        return _SATURDAY
    if any(word in text for word in ("evening", "tonight")):
        return _EVENING
    if not context:
        return (
            "There is nothing left in the memory file that bears on that, so this is a "
            "guess and you should treat it as one."
        )
    return (
        "The upstream model is unreachable, so this is a stand-in answer. Every stamp "
        "below is real: those are the memories that were handed over for this question."
    )
