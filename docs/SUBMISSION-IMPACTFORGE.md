# ImpactForge submission — Paper Trail

Same project as the NeuralSprint entry (`docs/SUBMISSION.md`), re-angled for
ImpactForge's weights: Build Quality 30 / **Real-World Impact 25** / Creativity 20 /
UX 15 / Clarity 10. Reuse that file's *How I built it*, *Challenges*, *Built with*,
proof-of-work and demo script verbatim. Replace the top framing with the below, and
paste the **Impact statement** into ImpactForge's required field.

---

## Project name

Paper Trail

## Elevator pitch (200 char limit)

AI assistants remember things about you that you never agreed to, can't inspect, and can't
remove one at a time. Paper Trail is a memory an assistant can use but the person it's about
actually controls.

## Try it out

- Live: https://trail.opxz.dev — no sign-up, no key, nothing to install
- Source: https://github.com/opx0-hackathon/paper-trail

---

## The problem (lead with this)

Hundreds of millions of people now talk to an assistant that remembers them. ChatGPT, Claude,
Gemini, every companion app — all shipped a memory feature in the last two years, and all of
them keep the same power on the same side of the table. The assistant decides what to store
about you. You cannot see why it answered the way it did. And when it holds something you
regret telling it — a diagnosis, a income figure, a thing you said in a bad week — your only
control is a switch that erases *everything* or nothing.

This is not a niche developer concern. It is a consumer-protection gap the size of the entire
consumer-AI market, and it lands hardest on the people with the most to lose from a leak: someone
managing a health condition, a domestic-abuse survivor whose location must never surface, a
teenager, anyone in a country where a belief or an orientation is dangerous to record. The
memory field in 2026 — Mem0, Zep, Letta and the rest — is a race to make *agents remember
better*. Nobody is building the other half: a memory that is answerable to the person it
describes.

## The solution

Paper Trail is that half. It is a personal memory file an assistant can read — but the person
it is about holds it, and three things are true that are true of no shipped assistant memory:

1. **Nothing is read without a receipt.** Every time a value is handed to the model, a row is
   written to a ledger *in the same database transaction as the read*. Not the model's account
   of what it used — the actual handover, logged by the code that does the handing. You can
   watch the ledger fill up as you talk.

2. **You can remove one memory without wiping the rest.** Pull a single fact off an answer and
   the question is re-answered without it, in one click. Revocation you can see working, not a
   settings toggle you have to trust.

3. **The sensitive stuff is treated differently, structurally.** A health fact or a belief is a
   "special category": it can never ride along inside another request, never travel on a share
   link, and is stamped separately when you do grant it. A figure you'd rather not disclose can
   be marked "attested" — the assistant is told it is *confirmed* without ever seeing the number.

And the governance follows you: mount the same file in Claude over MCP and an external agent
gets the exact same rules — ask, receipt, grant, revoke — because there is one policy engine,
not one per surface.

## Who this helps, concretely

- **Someone with a chronic condition** can let an assistant help plan meals or workouts while
  the diagnosis itself stays a protected category that is refused by default and logged when
  used.
- **A person rebuilding after an abusive relationship** can hand a caseworker a share link over
  two specific facts that expires in an hour and dies on revoke — without exposing the file.
- **Anyone** gets, for the first time, an answer to "why did it say that?" that is a receipt
  rather than a reassurance.

The demo makes this legible in sixty seconds to a non-technical person: ask what to cook, pull
the "kitchen equipment" memory off, and watch the advice change to assume a pan the persona
doesn't own. The abstract promise — *you control what it knows* — becomes something you see move.

---

## Impact statement (paste into ImpactForge's required field)

Assistant memory is now a mainstream consumer feature and a one-sided one: the system decides
what to keep about a person, that person can't see how it was used, and can't remove one thing
without wiping all of it. The harm is not hypothetical — it concentrates on people for whom a
recorded health condition, belief, location, or orientation is genuinely dangerous.

Paper Trail moves the control to the person the memory is about, and proves it rather than
promising it. Every read leaves a receipt written in the same transaction as the read, so the
audit trail cannot be falsified even by the model itself. Any single memory is revocable and
you can watch an answer change once it's gone. Special categories (health, beliefs) are refused
by default and can never leak through a share. The same guarantees hold when the file is mounted
into another assistant over MCP, so the protection travels with the person instead of ending at
one app's boundary.

It is live, free, requires no account, and works on a phone — so the person with the most to
lose does not need to be a developer to use it. The mechanism is small enough to audit: six pure
functions, ~100 lines, backed by 79 tests that read as the specification. This is a working
demonstration that consumer-AI memory can be accountable to its subject without giving up its
usefulness — a template the assistants people already use could adopt.

---

## Everything else

Reuse `docs/SUBMISSION.md` sections *How I built it*, *Challenges I ran into*,
*Accomplishments*, *What I learned*, *What's next*, *Provenance*, *Proof of work*, and the
demo script — all unchanged. Team: solo.
