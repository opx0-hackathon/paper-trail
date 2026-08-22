# Paper Trail over MCP

The agent-facing surface is the same file, under the same rules. An assistant somewhere
else can see what a memory is *about* for free. It cannot see what a memory *holds* until
the holder says so, and every attempt is written to the ledger whether it succeeds or not.

## Endpoint

```
POST https://trail.opxz.dev/mcp/{token}/{tool}
```

The token is minted per memory file from **Access → Connect an assistant**. It lives as
long as the session does, and it grants nothing on its own.

Point a client at it:

```json
{
  "mcpServers": {
    "paper-trail": {
      "type": "http",
      "url": "https://trail.opxz.dev/mcp/YOUR-TOKEN"
    }
  }
}
```

## Tools

### `describe`

```json
{}
```

Returns every live memory as a path and a subject — `diet.style`, "what I eat and what I
don't" — and never a value. This is what the scope call sees in the browser too.

### `request_context`

```json
{ "paths": ["diet.style", "budget.weekly"], "purpose": "planning dinner" }
```

For any path a standing grant already covers, the projected value comes back and a `read`
receipt is written in the same transaction. For everything else the reply is:

```json
{ "status": "pending", "id": "…", "paths": ["…"] }
```

and the holder sees a card asking whether to allow it once, for the session, or not at
all. A `REQUEST` receipt is written either way, so an assistant cannot ask quietly.

Three things this refuses outright, before any grant is consulted:

- a path that does not exist, or has been revoked
- a special category riding along with ordinary paths — it has to be its own request
- an attested memory as a figure; it projects as `confirmed: true` and never as the number

### `propose_memory`

```json
{ "path": "routine.gym", "value": "Tuesdays and Thursdays", "note": "when I exercise" }
```

Offers a fact. It never writes. The holder keeps it or declines it, and declining leaves
a receipt rather than nothing.

## What a grant is

Approving a request *for the session* writes a grant row: an app name, a path list, an
expiry, and a running count of how many times it has been read. It appears under
**Access**, it is revocable in one click, and revoking it takes effect on the next call —
there is no cached copy on the assistant's side that survives it.

## What never travels

- A special category never goes onto a share link at all.
- An attested value never leaves the store; only the confirmation does.
- Nothing at all after the session is purged, which happens 24 hours after it was made.
