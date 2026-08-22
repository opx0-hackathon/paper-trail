import { useState } from "react";

const TOOLS = [
  {
    name: "describe",
    args: "{}",
    does: "Every memory's path and subject. Never a value.",
  },
  {
    name: "request_context",
    args: '{ "paths": ["diet.style"], "purpose": "why you need it" }',
    does: "Projected values for anything a standing grant covers. Everything else comes back as a pending request the holder has to answer, and a REQUEST receipt is written either way.",
  },
  {
    name: "propose_memory",
    args: '{ "path": "routine.gym", "value": "…", "note": "…" }',
    does: "Offers a fact for the file. It never writes; the holder keeps it or does not.",
  },
];

interface Props {
  token: string | null;
  onConnect: () => void;
}

export function McpPanel({ token, onConnect }: Props) {
  const [copied, setCopied] = useState("");
  const base = token ? `${window.location.origin}/mcp/${token}` : "";

  const config = `{
  "mcpServers": {
    "paper-trail": {
      "type": "http",
      "url": "${base || "https://trail.opxz.dev/mcp/YOUR-TOKEN"}"
    }
  }
}`;

  const copy = (what: string, text: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(what);
      window.setTimeout(() => setCopied(""), 1600);
    });
  };

  return (
    <section className="mcp" id="mcp">
      <div className="flow-head">
        <span className="eyebrow">the same rules, from anywhere</span>
        <h2 className="big">An assistant elsewhere gets a request, not a copy.</h2>
        <p>
          Mount this file over MCP and every rule on this page still holds. Subjects travel freely.
          A value only moves after the holder says so, and the ledger records it exactly as it
          records a read made here.
        </p>
      </div>

      <div className="mcp-grid">
        <div className="card mcp-tools">
          <div className="label">three tools, and that is all there is</div>
          {TOOLS.map((tool) => (
            <div className="tool" key={tool.name}>
              <code className="mono tool-name">{tool.name}</code>
              <code className="mono tool-args">{tool.args}</code>
              <p>{tool.does}</p>
            </div>
          ))}
        </div>

        <div className="card mcp-wire">
          <div className="label">point a client at it</div>
          {token ? (
            <>
              <p className="privacy">
                This endpoint is yours, it lasts as long as this session, and revoking a grant kills
                it for the assistant holding it.
              </p>
              <pre className="mono snippet">{base}</pre>
              <div className="row">
                <button className="ghost" type="button" onClick={() => copy("url", base)}>
                  {copied === "url" ? "Copied" : "Copy endpoint"}
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="privacy">
                Connecting mints a token bound to this file. Nothing is handed over by minting it.
              </p>
              <div className="row">
                <button className="ghost" type="button" onClick={onConnect}>
                  Connect an assistant
                </button>
              </div>
            </>
          )}

          <div className="label" style={{ marginTop: 18 }}>
            claude_desktop_config.json
          </div>
          <pre className="mono snippet">{config}</pre>
          <div className="row">
            <button className="ghost" type="button" onClick={() => copy("config", config)}>
              {copied === "config" ? "Copied" : "Copy config"}
            </button>
            <a
              className="ghost"
              href="https://github.com/opx0/paper-trail/blob/main/docs/MCP.md"
              target="_blank"
              rel="noreferrer"
            >
              Read the contract
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
