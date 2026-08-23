"""The model client. Two calls per turn: what is needed, then the answer.

The first call is shown only what each memory is about, never what it holds, so it cannot
leak the thing it is asking permission for. This module asks and parses; policy decides.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from papertrail.models import Suggestion

log = logging.getLogger("papertrail.llm")

PROMPTS_DIR = Path(os.environ.get("PAPERTRAIL_PROMPTS", "prompts"))


def load_prompt(name: str) -> str:
    """Load a prompt from prompts/<name>.md. Trailing whitespace stripped."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").rstrip()


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

SCOPE_SYSTEM = load_prompt("scope")
SUGGEST_SYSTEM = load_prompt("suggest")
ANSWER_SYSTEM = load_prompt("answer")

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
            purpose="scope",
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
            purpose="suggest",
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
            purpose="answer",
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
        started = time.perf_counter()
        first_ms: float | None = None
        pieces = 0
        try:
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
                        if first_ms is None:
                            first_ms = (time.perf_counter() - started) * 1000
                        pieces += 1
                        yield piece
        finally:
            _log_call(
                "stream",
                self.model,
                usage={},
                ms=(time.perf_counter() - started) * 1000,
                extra={
                    "first_token_ms": int(first_ms) if first_ms is not None else -1,
                    "pieces": pieces,
                },
            )

    async def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        *,
        purpose: str,
    ) -> str:
        started = time.perf_counter()
        usage: dict[str, object] = {}
        err = ""
        try:
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
            usage = payload.get("usage") or {}
            content = str(payload["choices"][0]["message"]["content"] or "").strip()
            if not content:
                raise ValueError("the model returned nothing")
            return content
        except (httpx.HTTPError, ValueError) as exc:
            err = type(exc).__name__
            raise
        finally:
            _log_call(purpose, self.model, usage, (time.perf_counter() - started) * 1000, err=err)

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


def _log_call(
    purpose: str,
    model: str,
    usage: Mapping[str, object],
    ms: float,
    *,
    err: str = "",
    extra: Mapping[str, object] | None = None,
) -> None:
    """One JSON line per LLM call. Grep with `journalctl -o json | jq`."""

    def _int(x: object) -> int:
        if isinstance(x, int | float):
            return int(x)
        return 0

    record: dict[str, object] = {
        "kind": "llm_call",
        "purpose": purpose,
        "model": model,
        "in_toks": _int(usage.get("prompt_tokens", 0)),
        "out_toks": _int(usage.get("completion_tokens", 0)),
        "ms": int(ms),
    }
    if err:
        record["error"] = err
    if extra:
        record.update(extra)
    log.info(json.dumps(record))


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
