"""The guarantees, one test per property, named so a failure explains itself.

The claim this project makes is that the stamps under an answer are a record of what was
handed to the model rather than the model's account of what it used. Three tests below
are that claim: the scope call never sees a value, an attested memory yields proof only,
and a read and its receipt are one transaction or neither.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time

import pytest

from papertrail import export, extract, llm, mcp, policy, turn
from papertrail.models import ErrorCode, Memory, PaperTrailError, ReceiptAction
from papertrail.seed import SEED
from papertrail.store import Store

NOW = 1_760_000_000.0


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.db")


@pytest.fixture
def session(store):
    store.open_session("s1", NOW)
    store.seed("s1", NOW)
    return "s1"


def test_a_new_visitor_starts_with_an_empty_file(store):
    """Bringing your own file must not mean inheriting somebody else's."""
    store.open_session("fresh", NOW)
    assert store.memories("fresh") == {}
    assert store.live("fresh") == []


def test_seeding_fills_an_empty_file_once_and_never_twice(store):
    store.open_session("s2", NOW)
    assert store.seed("s2", NOW) is True
    assert len(store.memories("s2")) == len(SEED)
    assert store.seed("s2", NOW) is False
    assert len(store.memories("s2")) == len(SEED)


def test_seeding_refuses_a_file_that_already_holds_something(store):
    """An imported file is never quietly topped up with someone else's memories."""
    store.open_session("mine", NOW)
    store.remember("mine", Memory(path="work.role", value="Backend.", note="what I do"), NOW)
    assert store.seed("mine", NOW) is False
    assert list(store.memories("mine")) == ["work.role"]


def test_scope_prompt_never_contains_a_memory_value(store, session):
    """The first call is shown what each memory is about, never what it holds."""
    live = store.live(session)
    prompt = llm.scope_prompt("What should I cook tonight?", policy.labels_for_scope(live))
    for memory in live:
        assert memory.path in prompt, f"{memory.path} should be offered by name"
        assert memory.value not in prompt, f"{memory.path} leaked its value into the scope call"


def test_attested_memory_yields_proof_and_never_its_value(store, session):
    """`budget.weekly` reaches the model as confirmation that a budget exists."""
    memories = store.read(session, ["budget.weekly"], {}, NOW)
    context = policy.project(memories)
    assert context == {"budget.confirmed": True}
    assert "1200" not in str(context)


def test_special_category_refused_when_mixed_with_ordinary_memories(store, session):
    """Health does not ride along with a question about dinner; it needs its own ask."""
    known = store.memories(session)
    with pytest.raises(PaperTrailError) as caught:
        policy.validate_request(["diet.style", "health.condition"], known)
    assert caught.value.code is ErrorCode.MIXED_SENSITIVE


def test_special_category_alone_is_allowed(store, session):
    """Refusing the mix is not refusing the category."""
    known = store.memories(session)
    assert policy.validate_request(["health.condition"], known) == ["health.condition"]


def test_revoked_memory_is_never_offered_again(store, session):
    """Revocation removes a memory from the candidate list, not just from the answer."""
    assert store.revoke(session, "diet.style", NOW) is True
    offered = [row["path"] for row in policy.labels_for_scope(store.live(session))]
    assert "diet.style" not in offered
    assert store.read(session, ["diet.style"], {}, NOW) == []
    with pytest.raises(PaperTrailError) as caught:
        policy.validate_request(["diet.style"], store.memories(session))
    assert caught.value.code is ErrorCode.REVOKED


def test_a_read_that_cannot_be_stamped_does_not_happen(store, session):
    """The memories and their ledger lines go down together or not at all.

    Taking the ledger away is the bluntest way to prove it: the read raises rather than
    returning memories it could not account for, so an unstamped value never reaches a
    caller. This is the whole honesty of the project, enforced.
    """
    with sqlite3.connect(store.path) as con:
        con.execute("ALTER TABLE receipts RENAME TO receipts_taken_away")

    with pytest.raises(sqlite3.OperationalError):
        store.read(session, ["diet.style"], {}, NOW)

    with sqlite3.connect(store.path) as con:
        con.execute("ALTER TABLE receipts_taken_away RENAME TO receipts")
    assert store.receipts(session) == []


def test_every_read_leaves_exactly_one_receipt(store, session):
    store.read(session, ["diet.style", "location.city"], {"diet.style": "dinner"}, NOW)
    paths = [r.path for r in store.receipts(session)]
    assert sorted(paths) == ["diet.style", "location.city"]


def test_sessions_do_not_share_a_memory_file(store, session):
    """One visitor revoking a memory must not change what the next visitor sees."""
    store.open_session("s2", NOW)
    store.seed("s2", NOW)
    store.revoke(session, "diet.style", NOW)
    assert store.memories(session)["diet.style"].revoked is True
    assert store.memories("s2")["diet.style"].revoked is False
    assert store.receipts("s2") == []


def test_parse_needs_survives_a_fenced_reply():
    """A model that wraps its JSON in a code fence is still understood."""
    raw = '```json\n{"needs": [{"path": "diet.style", "purpose": "what they eat"}]}\n```'
    needs = llm.parse_needs(raw, ["diet.style", "budget.weekly"])
    assert [n.path for n in needs] == ["diet.style"]
    assert needs[0].purpose == "what they eat"


def test_parse_needs_ignores_paths_that_are_not_offered():
    """The model cannot widen its own scope by inventing a path."""
    raw = '{"needs": [{"path": "bank.password", "purpose": "trust me"}]}'
    assert llm.parse_needs(raw, ["diet.style"]) == []


def test_turn_without_a_model_still_stamps_what_it_used(store, session):
    """With no upstream configured the answer is cached, but the account is real."""
    result = asyncio.run(turn.run(store, session, "What should I cook tonight?", None))
    assert result.cached is True
    stamped = {s.path for s in result.stamps if s.kind != "refused"}
    assert "diet.style" in stamped
    read_paths = {r.path for r in store.receipts(session)}
    assert stamped <= read_paths


def test_turn_refuses_the_special_category_and_answers_anyway(store, session):
    """The health ask is refused and stamped; the dinner question still gets answered."""
    result = asyncio.run(turn.run(store, session, "What should I cook tonight?", None))
    refused = [s for s in result.stamps if s.kind == "refused"]
    assert [s.path for s in refused] == ["health.condition"]
    assert result.answer
    assert "health.condition" not in {s.path for s in result.stamps if s.kind != "refused"}


def test_revoking_a_memory_changes_the_answer(store, session):
    """The demonstration itself, as a test: pull the memory, get a different answer."""
    before = asyncio.run(turn.run(store, session, "What should I cook tonight?", None))
    store.revoke(session, "diet.style", NOW)
    after = asyncio.run(turn.run(store, session, "What should I cook tonight?", None))
    assert before.answer != after.answer
    assert "diet.style" not in {s.path for s in after.stamps}


def test_project_is_the_only_route_a_value_takes():
    """A plain memory passes its value; an attested one cannot, by construction."""
    plain = Memory("a.b", "secret", "about a")
    attested = Memory("c.d", "9999", "about c", attested=True)
    context = policy.project([plain, attested])
    assert context["a.b"] == "secret"
    assert context["c.confirmed"] is True
    assert "9999" not in str(context)


def test_the_seeded_file_has_one_attested_and_one_special_memory():
    """The demo depends on both existing; this fails loudly if the seed is edited."""
    assert sum(m.attested for m in SEED) == 1
    assert sum(m.sensitive for m in SEED) == 1


def test_asks_are_counted_for_the_rate_limit(store, session):
    assert store.count_ask(session) == 1
    assert store.count_ask(session) == 2


def test_restore_empties_the_file(store, session):
    store.revoke(session, "diet.style", NOW)
    store.restore(session, time.time())
    assert store.memories(session) == {}
    assert store.receipts(session) == []


# --- being asked first --------------------------------------------------------------


def test_propose_keeps_the_special_category_apart(store, session):
    """The proposal arrives already split, because the two are not one request."""
    proposal = asyncio.run(turn.propose(store, session, "What should I cook tonight?", None))
    assert "diet.style" in {a.path for a in proposal.ordinary}
    assert [a.path for a in proposal.special] == ["health.condition"]
    assert all(not a.sensitive for a in proposal.ordinary)


def test_propose_hands_nothing_over(store, session):
    """Asking is not reading: a proposal leaves the question stamped and no read at all."""
    asyncio.run(turn.propose(store, session, "What should I cook tonight?", None))
    actions = {r.action for r in store.receipts(session)}
    assert actions == {ReceiptAction.ASKED}


def test_a_granted_special_category_is_stamped_apart(store, session):
    """Granting it on purpose is a grant in its own right, and the ledger says so."""
    result = asyncio.run(
        turn.answer(
            store,
            session,
            "What should I cook tonight?",
            ["diet.style", "health.condition"],
            {},
            None,
        )
    )
    assert {s.path for s in result.stamps} == {"diet.style", "health.condition"}
    actions = {(r.action, r.path) for r in store.receipts(session)}
    assert (ReceiptAction.SENSITIVE_READ, "health.condition") in actions
    assert (ReceiptAction.READ, "diet.style") in actions


def test_answer_does_not_trust_the_browser_with_an_unknown_path(store, session):
    """The granted list comes from a client, so it is checked, not believed."""
    result = asyncio.run(
        turn.answer(store, session, "anything", ["bank.password", "diet.style"], {}, None)
    )
    assert "bank.password" not in {s.path for s in result.stamps if s.kind != "refused"}
    assert "diet.style" in {s.path for s in result.stamps}


def test_answer_does_not_trust_the_browser_with_a_revoked_path(store, session):
    """Revocation holds even against a client that asks for the memory by name."""
    store.revoke(session, "diet.style", NOW)
    result = asyncio.run(turn.answer(store, session, "anything", ["diet.style"], {}, None))
    assert [s.path for s in result.stamps if s.kind != "refused"] == []
    assert store.read(session, ["diet.style"], {}, NOW) == []


# --- what the assistant would like to keep ------------------------------------------


def test_a_kept_memory_appends_and_is_stamped(store, session):
    memory = Memory(path="routine.gym", value="Tuesdays and Thursdays.", note="when I exercise")
    assert store.remember(session, memory, NOW) is True
    file = store.memories(session)
    assert file["routine.gym"].value == "Tuesdays and Thursdays."
    assert len(file) == len(SEED) + 1
    assert (ReceiptAction.REMEMBERED, "routine.gym") in {
        (r.action, r.path) for r in store.receipts(session)
    }


def test_a_kept_memory_never_overwrites_one_already_there(store, session):
    """An assistant that can edit what it was already told can quietly rewrite you."""
    before = store.memories(session)["diet.style"].value
    clash = Memory(path="diet.style", value="Eats anything.", note="what I eat")
    assert store.remember(session, clash, NOW) is False
    assert store.memories(session)["diet.style"].value == before


def test_a_suggestion_must_be_a_plain_new_path():
    taken = [m.path for m in SEED]
    good = (
        '{"remember": {"path": "routine.gym", "value": "Tue and Thu.", "note": "when I exercise"}}'
    )
    assert llm.parse_suggestion(good, taken) is not None

    for bad, why in [
        ('{"remember": null}', "nothing durable"),
        ('{"remember": {"path": "diet.style", "value": "x", "note": "y"}}', "path already taken"),
        ('{"remember": {"path": "../etc/passwd", "value": "x", "note": "y"}}', "not a path"),
        ('{"remember": {"path": "routine.gym", "value": "", "note": "y"}}', "no value"),
        ("not json at all", "unparseable"),
    ]:
        assert llm.parse_suggestion(bad, taken) is None, why


def test_provenance_records_where_a_memory_came_from(store, session):
    assert store.memories(session)["diet.style"].source == "seeded"
    store.remember(
        session,
        Memory(path="routine.gym", value="Tue and Thu.", note="when I exercise", source="proposed"),
        NOW,
    )
    assert store.memories(session)["routine.gym"].source == "proposed"


def test_export_contains_every_memory_and_every_receipt(store, session):
    store.read(session, ["diet.style"], {"diet.style": "dinner"}, NOW)
    store.revoke(session, "location.city", NOW)
    memories = list(store.memories(session).values())
    receipts = store.receipts(session)

    payload = export.as_json(memories, receipts, "Arjun")
    assert {m["path"] for m in payload["memories"]} == {m.path for m in SEED}
    assert len(payload["ledger"]) == len(receipts)

    text = export.as_markdown(memories, receipts, "Arjun")
    assert "Vegetarian. No egg either." in text
    assert "location.city" in text
    assert "## Revoked" in text


def test_export_markdown_keeps_an_attested_value_out_of_nothing(store, session):
    """Export is for the holder, so it carries their own values, flagged as attested."""
    memories = list(store.memories(session).values())
    text = export.as_markdown(memories, store.receipts(session), "Arjun")
    assert "proof only" in text
    assert "1,200" in text


# --- bringing your own file ---------------------------------------------------------


def test_import_never_produces_an_unsafe_path():
    raw = json.dumps(
        {
            "memories": [
                {"path": "../../etc/passwd", "value": "x", "note": "y"},
                {"path": "Work.Role", "value": "x", "note": "y"},
                {"path": "nodot", "value": "x", "note": "y"},
                {"path": "work.role", "value": "Backend engineer.", "note": "what I do"},
            ]
        }
    )
    found = extract.parse(raw, [])
    assert [m.path for m in found] == ["work.role"]


def test_import_never_reuses_a_path_the_file_already_has():
    raw = json.dumps({"memories": [{"path": "diet.style", "value": "x", "note": "y"}]})
    assert extract.parse(raw, [m.path for m in SEED]) == []


def test_import_carries_the_special_and_attested_flags_through():
    raw = json.dumps(
        {
            "memories": [
                {
                    "path": "health.allergy",
                    "value": "Peanuts.",
                    "note": "a diagnosed medical condition",
                    "sensitive": True,
                },
                {
                    "path": "money.salary",
                    "value": "42000 a month.",
                    "note": "what I earn",
                    "attested": True,
                },
            ]
        }
    )
    found = {m.path: m for m in extract.parse(raw, [])}
    assert found["health.allergy"].sensitive is True
    assert found["money.salary"].attested is True
    assert all(m.source == "imported" for m in found.values())


def test_an_imported_special_category_still_cannot_ride_along(store, session):
    """A flag set by a model is not authority: policy re-checks it like any other."""
    imported = extract.parse(
        json.dumps(
            {
                "memories": [
                    {
                        "path": "health.allergy",
                        "value": "Peanuts.",
                        "note": "a diagnosed condition",
                        "sensitive": True,
                    }
                ]
            }
        ),
        [],
    )
    store.remember(session, imported[0], NOW)
    with pytest.raises(PaperTrailError) as caught:
        policy.validate_request(["diet.style", "health.allergy"], store.memories(session))
    assert caught.value.code is ErrorCode.MIXED_SENSITIVE


def test_an_attested_import_never_leaks_its_number(store, session):
    imported = extract.parse(
        json.dumps(
            {
                "memories": [
                    {
                        "path": "money.salary",
                        "value": "42000 a month.",
                        "note": "what I earn",
                        "attested": True,
                    }
                ]
            }
        ),
        [],
    )
    store.remember(session, imported[0], NOW)
    context = policy.project(store.read(session, ["money.salary"], {}, NOW))
    assert context == {"money.confirmed": True}
    assert "42000" not in str(context)


def test_import_falls_back_to_keywords_when_the_model_is_unreachable():
    text = "I'm a backend engineer in Bengaluru. I'm vegetarian and allergic to peanuts."
    found = {m.path: m for m in extract.fallback(text, [])}
    assert "diet.style" in found
    assert found["health.condition"].sensitive is True
    assert all(m.value for m in found.values())


def test_import_returns_nothing_rather_than_raising_on_rubbish():
    assert extract.parse("not json", []) == []
    assert extract.parse('{"memories": "not a list"}', []) == []


# --- handing someone a slice --------------------------------------------------------


def test_a_link_cannot_carry_a_special_category(store, session):
    """A link goes to someone the holder cannot supervise, so the rule is stricter."""
    with pytest.raises(PaperTrailError) as caught:
        policy.authorize_share(["diet.style", "health.condition"], store.memories(session))
    assert caught.value.code is ErrorCode.MIXED_SENSITIVE

    with pytest.raises(PaperTrailError):
        policy.authorize_share(["health.condition"], store.memories(session))


def test_a_link_cannot_cover_a_revoked_or_unknown_memory(store, session):
    store.revoke(session, "diet.style", NOW)
    for paths in (["diet.style"], ["bank.password"], []):
        with pytest.raises(PaperTrailError):
            policy.authorize_share(paths, store.memories(session))


def test_a_link_carries_its_subset_and_nothing_else(store, session):
    token = store.create_share(session, ["taste.music", "location.city"], 3600, NOW)
    opened = store.open_share(token, NOW)
    assert opened is not None
    holder, memories = opened
    assert holder == session
    assert {m.path for m in memories} == {"taste.music", "location.city"}


def test_opening_a_link_is_stamped_in_the_holders_ledger(store, session):
    token = store.create_share(session, ["taste.music"], 3600, NOW)
    store.open_share(token, NOW)
    store.open_share(token, NOW)
    actions = [r.action for r in store.receipts(session)]
    assert actions.count(ReceiptAction.VIEWED) == 2
    assert ReceiptAction.SHARED in actions


def test_a_revoked_link_returns_nothing(store, session):
    token = store.create_share(session, ["taste.music"], 3600, NOW)
    assert store.revoke_share(session, token, NOW) is True
    assert store.open_share(token, NOW) is None


def test_an_expired_link_returns_nothing(store, session):
    token = store.create_share(session, ["taste.music"], 60, NOW)
    assert store.open_share(token, NOW + 30) is not None
    assert store.open_share(token, NOW + 61) is None


def test_a_link_narrows_when_a_covered_memory_is_revoked(store, session):
    """Revocation reaches through a link that was minted before it."""
    token = store.create_share(session, ["taste.music", "location.city"], 3600, NOW)
    store.revoke(session, "taste.music", NOW)
    opened = store.open_share(token, NOW)
    assert opened is not None
    assert {m.path for m in opened[1]} == {"location.city"}


def test_only_the_holder_can_revoke_their_own_link(store, session):
    store.open_session("someone-else", NOW)
    token = store.create_share(session, ["taste.music"], 3600, NOW)
    assert store.revoke_share("someone-else", token, NOW) is False
    assert store.open_share(token, NOW) is not None


def test_a_shared_attested_memory_never_carries_its_value(store, session):
    """Hiding a value in the browser is not hiding it. The payload must not hold it."""
    from fastapi.testclient import TestClient

    from papertrail.app import app

    token = store.create_share(session, ["budget.weekly"], 3600, time.time())
    with TestClient(app) as client:
        client.app.state.store = store
        body = client.get(f"/api/shared/{token}").json()

    shared = body["memories"][0]
    assert shared["attested"] is True
    assert shared["value"] == ""
    assert "1,200" not in json.dumps(body)


# --- an assistant somewhere else ----------------------------------------------------


def test_an_agent_token_names_one_file_and_is_stable(store, session):
    token = store.agent_token(session, NOW)
    assert store.agent_token(session, NOW) == token
    assert store.session_for_agent(token) == session
    assert store.session_for_agent("not-a-token") is None


def test_list_context_shows_subjects_and_never_values(store, session):
    listed = mcp.describe(store, session)
    text = json.dumps(listed)
    for memory in store.live(session):
        assert memory.path in text
        assert memory.value not in text


def test_request_context_returns_pending_without_a_grant(store, session):
    result = mcp.request_context(store, session, "claude", ["diet.style"], "planning dinner")
    assert result["status"] == "pending"
    assert result["context"] == {}
    assert result["pending"]["paths"] == ["diet.style"]
    assert ReceiptAction.REQUESTED in {r.action for r in store.receipts(session)}


def test_a_standing_grant_lets_the_next_call_through(store, session):
    first = mcp.request_context(store, session, "claude", ["diet.style"], "dinner")
    assert mcp.approve(store, session, first["pending"]["id"], ["diet.style"], True) is True

    second = mcp.request_context(store, session, "claude", ["diet.style"], "dinner")
    assert second["status"] == "ok"
    assert second["context"] == {"diet.style": "Vegetarian. No egg either."}


def test_a_grant_covers_only_its_own_paths(store, session):
    first = mcp.request_context(store, session, "claude", ["diet.style"], "dinner")
    mcp.approve(store, session, first["pending"]["id"], ["diet.style"], True)

    wider = mcp.request_context(store, session, "claude", ["diet.style", "location.city"], "dinner")
    assert wider["status"] == "partial"
    assert list(wider["context"]) == ["diet.style"]
    assert wider["pending"]["paths"] == ["location.city"]


def test_revoking_a_grant_closes_the_door_again(store, session):
    first = mcp.request_context(store, session, "claude", ["diet.style"], "dinner")
    mcp.approve(store, session, first["pending"]["id"], ["diet.style"], True)
    grant = store.grants(session)[0]

    assert store.revoke_grant(session, grant.id, NOW) is True
    after = mcp.request_context(store, session, "claude", ["diet.style"], "dinner")
    assert after["status"] == "pending"
    assert after["context"] == {}


def test_a_granted_attested_memory_still_projects_as_proof(store, session):
    first = mcp.request_context(store, session, "claude", ["budget.weekly"], "shopping")
    mcp.approve(store, session, first["pending"]["id"], ["budget.weekly"], True)

    second = mcp.request_context(store, session, "claude", ["budget.weekly"], "shopping")
    assert second["context"] == {"budget.confirmed": True}
    assert "1,200" not in json.dumps(second)


def test_refusing_a_request_leaves_a_receipt_and_no_grant(store, session):
    first = mcp.request_context(store, session, "claude", ["diet.style"], "dinner")
    assert mcp.approve(store, session, first["pending"]["id"], [], False) is True
    assert store.grants(session) == []
    assert ReceiptAction.REFUSED in {r.action for r in store.receipts(session)}


def test_a_request_cannot_be_settled_twice(store, session):
    first = mcp.request_context(store, session, "claude", ["diet.style"], "dinner")
    request_id = first["pending"]["id"]
    assert mcp.approve(store, session, request_id, ["diet.style"], True) is True
    assert mcp.approve(store, session, request_id, ["diet.style"], True) is False


def test_an_agent_proposing_a_memory_never_writes_one(store, session):
    before = set(store.memories(session))
    result = mcp.propose_memory(
        store, session, "claude", "routine.gym", "Tuesdays and Thursdays.", "when I exercise"
    )
    assert result["status"] == "pending"
    assert set(store.memories(session)) == before
    assert ReceiptAction.SUGGESTED in {r.action for r in store.receipts(session)}


def test_an_agent_cannot_propose_a_malformed_or_existing_path(store, session):
    for path in ("../etc/passwd", "diet.style", "nodot"):
        assert mcp.propose_memory(store, session, "claude", path, "x", "y")["status"] == "refused"


def test_an_assistant_knocking_asks_rather_than_reads(store, session):
    """The demo knock has to be the real MCP path: a pending request, never a free read."""
    from fastapi.testclient import TestClient

    from papertrail.app import app

    with TestClient(app) as client:
        client.app.state.store = store
        client.cookies.set("pt_sid", session)
        body = client.post("/api/knock").json()

    assert [p["app"] for p in body["pending"]] == ["Claude Desktop"]
    assert "health.condition" not in body["pending"][0]["paths"]
    assert not [r for r in body["receipts"] if r["action"] in ("read", "sensitive_read")]


def test_an_assistant_cannot_knock_on_an_empty_file(store):
    """Nothing to ask for is not a pending request; it is a notice."""
    from fastapi.testclient import TestClient

    from papertrail.app import app

    store.open_session("bare", NOW)
    with TestClient(app) as client:
        client.app.state.store = store
        client.cookies.set("pt_sid", "bare")
        body = client.post("/api/knock").json()

    assert body["pending"] == []
    assert "notice" in body


def test_purge_removes_a_stale_session_and_everything_it_held(store, session):
    store.create_share(session, ["taste.music"], 3600, NOW)
    store.agent_token(session, NOW)
    store.open_request(session, "claude", ["diet.style"], "dinner", NOW)
    store.open_session("recent", NOW)

    assert store.purge(3600, NOW + 7200) == 2
    assert store.memories(session) == {}
    assert store.receipts(session) == []
    assert store.shares(session) == []
    assert store.pending(session) == []


def test_purge_leaves_a_live_session_alone(store, session):
    assert store.purge(3600, NOW + 60) == 0
    assert len(store.memories(session)) == len(SEED)


def test_migrations_add_missing_columns_to_an_older_database(tmp_path):
    """Boot-time migration runner catches up a DB from before a new column landed.

    Regression for the 2026-08-24 /api/state outage: the old code path used
    `CREATE TABLE IF NOT EXISTS` which never ALTERs, so a moved checkout with
    an older schema kept 500ing until the DB was wiped by hand.
    """
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, created_at REAL NOT NULL,"
        " asks INTEGER NOT NULL DEFAULT 0);"
        "CREATE TABLE memories (session_id TEXT, path TEXT, value TEXT, note TEXT,"
        " attested INT, sensitive INT, revoked INT, ordinal INT,"
        " PRIMARY KEY(session_id, path));"
    )
    con.commit()
    con.close()

    Store(path)  # boot triggers the migration runner

    with sqlite3.connect(path) as con:
        cols = [row[1] for row in con.execute("PRAGMA table_info(memories)")]
        applied = [row[0] for row in con.execute("SELECT id FROM _migrations ORDER BY id")]

    assert "source" in cols
    assert "created_at" in cols
    assert applied == [1, 2]
