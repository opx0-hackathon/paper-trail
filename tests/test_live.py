"""The one test that really calls the model.

Excluded from the default run because it needs a key and a network. It exists so the claim
that the scope call works against a real model is checked rather than asserted:

    LIVE=1 uv run pytest -m live
"""

from __future__ import annotations

import asyncio
import os

import pytest

from papertrail import llm, policy
from papertrail.store import Store

pytestmark = pytest.mark.live

NOW = 1_760_000_000.0


@pytest.fixture(autouse=True)
def _requires_a_key():
    llm.load_key_file()
    if not os.environ.get("LIVE") or not llm.configured():
        pytest.skip("set LIVE=1 and PAPERTRAIL_API_KEY to run the live test")


def test_a_real_model_asks_for_the_memories_a_dinner_question_needs(tmp_path):
    """The scope call comes back as usable JSON, naming paths that were actually offered."""
    store = Store(tmp_path / "live.db")
    store.open_session("live", NOW)
    labels = policy.labels_for_scope(store.live("live"))

    async def go():
        client = llm.Client()
        try:
            return await client.scope("What should I cook tonight?", labels)
        finally:
            await client.aclose()

    needs = asyncio.run(go())
    offered = {row["path"] for row in labels}
    assert needs, "a dinner question should need at least one memory"
    assert {n.path for n in needs} <= offered, "the model cannot widen its own scope"
    assert "diet.style" in {n.path for n in needs}
