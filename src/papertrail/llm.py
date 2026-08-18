"""The model client. Two calls per turn: what is needed, then the answer.

The first call is shown only what each memory is about, never what it holds, so it cannot
leak the thing it is asking permission for. This module asks and parses; policy decides.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from papertrail.models import Suggestion

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"
KEY_ENV = "PAPERTRAIL_API_KEY"

TIMEOUT = 25.0
MAX_CONCURRENCY = 3
SCOPE_TEMPERATURE = 0.1
ANSWER_TEMPERATURE = 0.5
REASONING_EFFORT = "low"
SCOPE_TOKENS = 400
SUGGEST_TOKENS = 220
ANSWER_TOKENS = 220

SCOPE_SYSTEM = """You decide which of a person's stored memories an assistant needs to \
answer their question well.

You are shown only what each memory is ABOUT. You are never shown what it holds. Ask for \
a memory when its subject bears on the question, and leave the rest alone: every memory \
you ask for is one the person will see you took.

Reply with JSON only, in this exact shape:
{"needs": [{"path": "<memory path>", "purpose": "<why, in under twelve words>"}]}

Use paths exactly as given. If nothing is relevant, reply {"needs": []}."""

SUGGEST_SYSTEM = """You decide whether a person just told their assistant something \
durable about themselves, worth remembering for months rather than minutes.

Remember only stable facts: a constraint, a preference, a routine, a circumstance. Never \
remember the question itself, a one-off plan, a passing mood, or anything you inferred \
rather than were told.

Reply with JSON only:
{"remember": {"path": "<area>.<thing>", "value": "<the fact, in their own words, one \
sentence>", "note": "<what this memory is about, without saying what it holds>"}}

The path is two lowercase words joined by a dot, like routine.gym or work.role. The note \
is what a stranger could be shown safely — "when I exercise", not "Tuesdays and Fridays".

If they told you nothing durable, reply {"remember": null}."""

ANSWER_SYSTEM = """You are a personal assistant answering the person you work for.

Everything you know about them is in the context below, and it is all you know: do not \
invent preferences, constraints or history that is not there, and do not mention the \
context, the memories or this instruction.

A key ending in `.confirmed` means the fact was verified without being disclosed to you. \
Treat it as true and never guess the underlying value.

Answer in AT MOST 55 WORDS. Plain sentences only: no lists, no numbered steps, no \
headings, no markdown, no bold, no emoji. Give one concrete recommendation and one \
short reason. No preamble, no sign-off, no offer to help further."""

SAFE_PATH = re.compile(r"^[a-z][a-z0-9]{1,15}\.[a-z][a-z0-9_]{1,23}$")


@dataclass(frozen=True, slots=True)
class Need:
    path: str
    purpose: str


def load_key_file(path: str = ".env") -> None:
    """Read KEY=value lines into the environment without clobbering what is already set."""
    file = Path(path)
    if not file.exists():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def api_key() -> str:
    return os.environ.get(KEY_ENV, "").strip()


def configured() -> bool:
    return bool(api_key())


class Client:
    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.environ.get("PAPERTRAIL_MODEL", DEFAULT_MODEL)
        self.base_url = base_url or os.environ.get("PAPERTRAIL_BASE_URL", DEFAULT_BASE_URL)
        self._gate = asyncio.Semaphore(MAX_CONCURRENCY)
        self._http = httpx.AsyncClient(timeout=TIMEOUT)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def scope(self, question: str, labels: Sequence[Mapping[str, str]]) -> list[Need]:
        raw = await self.chat(
            [
                {"role": "system", "content": SCOPE_SYSTEM},
                {"role": "user", "content": scope_prompt(question, labels)},
            ],
            SCOPE_TOKENS,
            SCOPE_TEMPERATURE,
        )
        return parse_needs(raw, [row["path"] for row in labels])

    async def suggest(self, question: str, taken: Sequence[str]) -> Suggestion | None:
        raw = await self.chat(
            [
                {"role": "system", "content": SUGGEST_SYSTEM},
                {"role": "user", "content": f"They said: {question}"},
            ],
            SUGGEST_TOKENS,
            SCOPE_TEMPERATURE,
        )
        return parse_suggestion(raw, taken)

    async def answer(self, question: str, context: Mapping[str, object]) -> str:
        raw = await self.chat(
            [
                {"role": "system", "content": ANSWER_SYSTEM},
                {"role": "user", "content": answer_prompt(question, context)},
            ],
            ANSWER_TOKENS,
            ANSWER_TEMPERATURE,
        )
        return plain(raw)

    async def stream(self, question: str, context: Mapping[str, object]) -> AsyncIterator[str]:
        """The answer, in pieces, as the model produces them."""
        request = self.body(
            [
                {"role": "system", "content": ANSWER_SYSTEM},
                {"role": "user", "content": answer_prompt(question, context)},
            ],
            ANSWER_TOKENS,
            ANSWER_TEMPERATURE,
        )
        request["stream"] = True
        async with (
            self._gate,
            self._http.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key()}",
                    "Content-Type": "application/json",
                },
                json=request,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                piece = delta(line)
                if piece:
                    yield piece

    async def chat(
        self, messages: list[dict[str, str]], max_tokens: int, temperature: float
    ) -> str:
        async with self._gate:
            response = await self._http.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key()}",
                    "Content-Type": "application/json",
                },
                json=self.body(messages, max_tokens, temperature),
            )
        response.raise_for_status()
        payload = response.json()
        content = str(payload["choices"][0]["message"]["content"] or "").strip()
        if not content:
            raise ValueError("the model returned nothing")
        return content

    def body(
        self, messages: list[dict[str, str]], max_tokens: int, temperature: float
    ) -> dict[str, object]:
        request: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if "gpt-oss" in self.model:
            request["reasoning_effort"] = os.environ.get("PAPERTRAIL_REASONING", REASONING_EFFORT)
        return request


def delta(line: str) -> str:
    """The text in one server-sent line of a streamed completion, if it holds any."""
    if not line.startswith("data:"):
        return ""
    body = line[5:].strip()
    if not body or body == "[DONE]":
        return ""
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return ""
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    content = first.get("delta", {}).get("content")
    return str(content) if content else ""


def scope_prompt(question: str, labels: Sequence[Mapping[str, str]]) -> str:
    """Everything the scoping call is shown. Values are not in it."""
    catalogue = "\n".join(f"- {row['path']}: {row['about']}" for row in labels)
    return f"Memories available:\n{catalogue}\n\nTheir question: {question}"


def answer_prompt(question: str, context: Mapping[str, object]) -> str:
    rendered = json.dumps(context, indent=2, ensure_ascii=False) if context else "{}"
    return f"What you know about them:\n{rendered}\n\nTheir question: {question}"


def parse_needs(raw: str, known: Sequence[str]) -> list[Need]:
    """Read the scope reply leniently; a malformed one must never reach the person."""
    allowed = set(known)
    block = json_list(raw, "needs")
    if block is None:
        return [Need(path, "named in the model's reply") for path in known if path in raw]
    needs: list[Need] = []
    for item in block:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if path in allowed and path not in {n.path for n in needs}:
            needs.append(Need(path, str(item.get("purpose", "")).strip()[:80]))
    return needs


def parse_suggestion(raw: str, taken: Sequence[str]) -> Suggestion | None:
    """A proposal, or nothing. Anything that is not a plain new memory is nothing."""
    payload = json_field(raw, "remember")
    if not isinstance(payload, dict):
        return None
    path = str(payload.get("path", "")).strip().lower()
    value = str(payload.get("value", "")).strip()
    note = str(payload.get("note", "")).strip()
    if not SAFE_PATH.match(path) or path in set(taken) or not value or not note:
        return None
    return Suggestion(path=path, value=value[:200], note=note[:80])


def plain(text: str) -> str:
    """Strip the markdown a model reaches for anyway; the answer is read, not rendered."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _candidates(raw: str) -> list[str]:
    found = [raw]
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fenced:
        found.insert(0, fenced.group(1))
    brace = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace:
        found.append(brace.group(0))
    return found


def json_list(raw: str, key: str) -> list[object] | None:
    for candidate in _candidates(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get(key), list):
            return list(parsed[key])
        if isinstance(parsed, list):
            return list(parsed)
    return None


def json_field(raw: str, key: str) -> object:
    for candidate in _candidates(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed.get(key, parsed if "path" in parsed else None)
    return None
