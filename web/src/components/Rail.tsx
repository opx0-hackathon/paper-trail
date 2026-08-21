import { useState } from "react";
import { AgentPanel } from "./AgentPanel";
import { Ledger } from "./Ledger";
import { MemoryFile } from "./MemoryFile";
import { ShareDialog } from "./ShareDialog";
import type { FileState } from "../types";

type Tab = "memory" | "ledger" | "access";

interface Props {
  file: FileState;
  agentToken: string | null;
  exportUrl: (format: "json" | "markdown") => string;
  onConnect: () => void;
  onKnock: () => void;
  onSettle: (id: string, paths: string[], standing: boolean) => void;
  onUngrant: (id: string) => void;
  onShare: (paths: string[]) => Promise<string | null>;
  onUnshare: (token: string) => void;
}

export function Rail({
  file,
  agentToken,
  exportUrl,
  onConnect,
  onKnock,
  onSettle,
  onUngrant,
  onShare,
  onUnshare,
}: Props) {
  const [tab, setTab] = useState<Tab>("memory");
  const [focus, setFocus] = useState<string | null>(null);

  const trace = (path: string) => {
    setFocus(path);
    setTab("ledger");
  };

  const live = file.memories.filter((memory) => !memory.revoked).length;
  const access =
    file.grants.filter((grant) => !grant.revoked).length +
    file.shares.filter((share) => !share.revoked).length;

  const button = (key: Tab, label: string, badge?: number) => (
    <button
      type="button"
      role="tab"
      aria-selected={tab === key}
      onClick={() => {
        setTab(key);
        setFocus(null);
      }}
    >
      {label}
      {badge ? <span className="count quiet">{badge}</span> : null}
    </button>
  );

  return (
    <div className="rail">
      {file.pending.length > 0 && (
        <AgentPanel
          token={agentToken}
          pending={file.pending}
          grants={file.grants}
          onConnect={onConnect}
          onKnock={onKnock}
          onSettle={onSettle}
          onUngrant={onUngrant}
          requestsOnly
        />
      )}

      <div
        className="tabs"
        role="tablist"
        style={{ ["--tab" as string]: ["memory", "ledger", "access"].indexOf(tab) }}
      >
        {button("memory", "Memory", live)}
        {button("ledger", "Ledger", file.receipts.length)}
        {button("access", "Access", access)}
      </div>

      {tab === "memory" && (
        <MemoryFile memories={file.memories} holder={file.holder} onTrace={trace} />
      )}
      {tab === "ledger" && (
        <Ledger receipts={file.receipts} focus={focus} onClearFocus={() => setFocus(null)} />
      )}
      {tab === "access" && (
        <>
          <AgentPanel
            token={agentToken}
            pending={[]}
            grants={file.grants}
            onConnect={onConnect}
            onKnock={onKnock}
            onSettle={onSettle}
            onUngrant={onUngrant}
          />
          <ShareDialog
            memories={file.memories}
            shares={file.shares}
            onShare={onShare}
            onUnshare={onUnshare}
          />
          <div className="panel">
            <div className="foot">
              <span className="eyebrow" style={{ marginRight: "auto" }}>
                take it with you
              </span>
              <span className="toolbar">
                <a href={exportUrl("markdown")} download>
                  Markdown
                </a>
                <a href={exportUrl("json")} download>
                  JSON
                </a>
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
