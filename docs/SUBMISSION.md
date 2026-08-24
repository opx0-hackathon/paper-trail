# NeuralSprint submission — Paper Trail

Copy-paste into the Devpost form. Field names match Devpost's.

---

## Project name

Paper Trail

## Elevator pitch (200 char limit)

AI memory decides what to keep and can't prove what it used. Paper Trail is a memory file you own — nothing read without a receipt, any one memory revocable, and the same rules travel over MCP.

## Try it out (links)

- Live demo: https://trail.opxz.dev — no sign-up, no key, nothing to install
- Source: https://github.com/opx0-hackathon/paper-trail
- Agent-facing contract: https://github.com/opx0-hackathon/paper-trail/blob/main/docs/MCP.md

## Built with (tags)

`python` `fastapi` `sqlite` `react` `typescript` `vite` `groq` `gpt-oss-20b` `mcp` `server-sent-events` `docker` `caddy` `github-actions` `pytest` `vitest` `mypy` `ruff`

---

## About the project

### Inspiration

Every assistant with a memory feature has the same three holes in it. You cannot see *why* it
said what it said. You cannot remove one thing it knows without wiping all of it. And you never
agreed to any of what it decided to keep.

The 2026 AI-memory field — Mem0, Zep, Letta, MemPalace and the rest — is developer
infrastructure optimising for *agents remembering better*. Every one of them is a service an
application buys. Not one is accountable to the person being remembered.

They make agents remember. Paper Trail makes remembering answerable to the person it is about.

### What it does

**Bring anything, get a memory file.** Paste a bio, a résumé, an export from another assistant,
or three sentences. One model call proposes candidate memories, each classified as a special
category (health, beliefs) or an attested figure (a salary, a budget), and nothing is written
until you tick it. Policy re-checks every flag rather than trusting the model, so an imported
health fact still cannot ride along with dinner preferences.

**Every answer says what it cost.** A turn is two model calls, not one. The first sees only what
each memory is *about* — "a diagnosed medical condition", never "coeliac" — and has to say which
ones it needs and why. Only then is anything projected and handed over. Stamps appear at about
0.6s, before the answer starts streaming, so you see what the model was given and then watch it
work from precisely that.

**Pull a memory off and watch the answer change.** The demo persona lives in a hostel with a
kettle and a microwave. Ask what to cook and you get microwave khichdi. Pull `kitchen.equipment`
off the stamp row and the same question comes back telling him to soften an onion in a pan. He
has no pan. Revocation you can see working in one click is a very different thing from a
settings toggle you have to trust.

**Be asked first.** Tick "ask me first" and a question stops after the scope call: the request
appears as a card, each memory with the reason the model gave, nothing yet out of the database.
The special category sits in its own block, unticked. Grant it deliberately and it becomes a
second independent request, stamped `sensitive_read` apart from everything beside it.

**Hand someone a slice, or take the whole thing with you.** A share link covers a subset,
expires in an hour, counts every open, and dies the moment you revoke it. The rule on a link is
stricter than the rule on a request: a special category cannot travel on one at all, and an
attested value never enters the payload. Export gives you the whole file and its ledger as JSON
or Markdown.

**The governance follows you into other assistants.** Mount the file over MCP. `describe` shows
subjects and never values. `request_context` returns projected values for whatever a standing
grant covers and a pending request for everything else. `propose_memory` offers a memory and
never writes one. Standing grants exist because consent that interrupts a person on every call
is consent they will switch off — so a grant is listed, counted, and revocable, and the next
call after a revoke is pending again.

### The claim, and why you should not take my word for it

Plenty of projects answer the explainability hole by asking the model which facts it used and
printing the reply. That is the model's account of itself: unverifiable, and wrong often enough
to matter.

**The receipt is written by the code that hands the value over, not claimed by the model
afterwards.** The model cannot see a memory that was never placed in its prompt, and the stamps
under an answer are rendered from rows written in the same database transaction as the read.

That is testable rather than promised, so it is tested. Three tests hold the line:

- `test_scope_prompt_never_contains_a_memory_value` — the scoping call is handed subjects only
- `test_attested_memory_yields_proof_and_never_its_value` — an attested salary reaches the model
  as `budget.confirmed: true`, never as the number
- `test_a_read_that_cannot_be_stamped_does_not_happen` — drop the receipts table and the read
  raises instead of quietly succeeding

That last one is the whole architecture in one test. The read and its receipt are the same
transaction, so losing the receipt loses the read.

### How I built it

Six pure functions carry the entire model, in `policy.py` — about 100 lines, no I/O, no state:

| Function | What it guarantees |
|---|---|
| `labels_for_scope` | the scoping call is shown what a memory is about, never what it holds |
| `validate_request` | unknown, revoked, and ride-along special categories are all refused |
| `split_by_category` | a special category becomes its own request rather than a dead end |
| `authorize_share` | a link carries live, ordinary memories only |
| `project` | the only route a value takes to a model; attested yields proof, never value |
| `stamps` | the row under an answer is built from what was handed over, not what was claimed |

Everything else is deliberately thin. `llm.py` and `extract.py` ask and parse and decide nothing.
`turn.py` is the only module that knows the order of the steps, split into `propose` and `answer`
so there is a moment where nothing has been handed over yet and a person can still say no.
`store.py` is the only module that speaks SQL, and every read and write puts its receipt down in
the same transaction as the effect. `mcp.py` and `app.py` hold no rules at all — which is why the
browser and an external agent get identical guarantees rather than two implementations that drift.

**Stack.** FastAPI, SQLite (stdlib `sqlite3`, no ORM), and `openai/gpt-oss-20b` on Groq at
`reasoning_effort: low`. React 19, Vite, TypeScript under `strict` with
`noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`; one `useReducer`, no state library,
no router. Answers stream over SSE. One Docker container on loopback behind Caddy, shipped by
GitHub Actions over SSH; CI runs ruff, mypy strict, pytest, prettier, tsc, vitest and a
production build on every push, and the deploy waits on it.

**The model was chosen by measurement, not vibes:**

| Model | Scope call | Result |
|---|---|---|
| `openai/gpt-oss-20b` | 0.64s | clean JSON, asks for six memories including the special category |
| `openai/gpt-oss-120b` | 0.53s | clean JSON, asks for two — a thinner, less honest stamp row |
| `qwen/qwen3.6-27b` | 1.27s | leaks `<think>` blocks, spends the budget reasoning |
| `groq/compound-mini` | 1.23s | clean JSON, four memories |

The bigger model was faster and worse for this job: a scope call that under-asks produces a
stamp row that under-reports, which is exactly the failure this project exists to prevent.

### Challenges I ran into

**Proving a negative.** "The model never saw this value" is not something you can demonstrate by
looking at output. It had to become a structural property — one function is the only route a
value takes to a model — and then a test that asserts the prompt string does not contain it.

**Consent that people will actually leave switched on.** The first version asked before every
single read. It was correct and unusable. Standing grants with a TTL, a read count, and a visible
revoke button are the compromise: the interruption happens once, and the accountability keeps
running afterwards.

**A public demo of a revocation feature, with no accounts.** Every row is keyed by session, so
your revoke cannot change what the next visitor sees. Sessions and everything they hold are
purged after 24 hours, because visitors paste personal text into this and there is nobody to ask
for a deletion.

**A model that is allowed to be wrong.** The scope call can hallucinate a path, over-ask, or
return unparseable JSON. `parse_needs` intersects with the offered set, `validate_request`
refuses the rest, and if the upstream is unreachable the app serves clearly labelled stand-in
answers while every mechanic — scoping, refusals, receipts, revocation, proposals — still runs
for real against them. The governance does not depend on the model behaving.

**The deploy lying about itself.** The health poll ran under `set -euo pipefail` with an
unguarded `curl`, so the first connection refused by a still-booting container killed the script
before its own retry loop. Deploys had been succeeding while the job reported failure. Fixed by
guarding both probes.

### Accomplishments that I'm proud of

- The honesty invariant is enforced by a database transaction, not by a prompt.
- 60 Python tests and 19 TypeScript ones, written as the specification: one per property, named
  so a failure explains itself rather than needing a debugger.
- ruff, mypy `strict` and TypeScript `strict` all clean, gating the deploy.
- The whole authorization model is six pure functions you can read in five minutes and check
  against the promises on the landing page.
- It is genuinely live, with no sign-up and no key, and the interesting parts — the stamp row,
  revocation, ask-me-first, sharing — work on a phone.

### What I learned

Consent is a UI problem before it is a policy problem. And an audit trail that the audited
component writes about itself is not an audit trail — the only receipts worth anything are the
ones produced by the code doing the handing over, in the same transaction as the effect.

### What's next

Conflict detection: a new memory that contradicts an old one should be surfaced rather than
appended beside it. That is the failure mode of every memory system that only ever adds.

### Provenance

Built independently in August 2026, during the hackathon window. The policy and receipt engine
is adapted from **Agent Visa**, my own earlier MIT-licensed project — `project()`,
`validate_request()`, the same-transaction receipt discipline, and the visual language.
Everything else here was written for Paper Trail. This note is here so nobody has to take that
on trust.

Not built: accounts.

---

## Proof of work

Screenshots in `docs/`, in the order a judge should look at them:

| File | Shows |
|---|---|
| `g1-landing.png` | the landing page and the memory file |
| `g2-candidates.png` | five pasted sentences become candidate memories, none kept yet |
| `g7-keep.png` | ticking what to keep |
| `g4-stamps.png` | the stamp row under an answer — what was handed over, and why |
| `g5-revoked.png` | the same question re-answered after one memory is pulled off |
| `g6-asking.png` | ask-me-first: the consent card, special category unticked and apart |
| `g8-share.png` | a share link over a subset, counted and revocable |
| `g11-mcp.png` | the MCP panel: token, endpoint, client config |
| `g10-flow.png` | the explainer diagram of the two-call turn |
| `g9-mobile.png` | mobile |

---

## 60-second demo script (for the video, or for a judge with the live link)

1. Open https://trail.opxz.dev and click **"Try a ready-made file"** — a student in a hostel
   room, already filled in. (Or **"Bring your own"** and paste five sentences about yourself.)
2. Ask **"what should I cook tonight?"** Watch the stamp row land *before* the text streams:
   it names each memory handed over and the reason the model gave for wanting it.
3. Click the **✕ on `kitchen.equipment`** in the stamp row. The same question is answered again
   without it, and the advice now assumes a pan the persona does not own.
4. Tick **ask me first**, ask **"am I eating enough protein?"** The turn stops on a consent card.
   The health memory sits in its own block, unticked. Grant it — it is stamped `sensitive_read`,
   separately.
5. Open the **Ledger** tab: every ask, read, refusal, grant and revoke, in order.
6. **Share** two memories, open the link in a private window, come back and see the view counted.
   Revoke it; reload the link; it is gone.
7. Paste your own three sentences into **import** to see candidates proposed and nothing kept
   until you say so.

---

## Team

Solo. All design, backend, frontend, tests, infrastructure and deployment.
