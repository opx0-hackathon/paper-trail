import { useState } from "react";
import type { Memory, Share } from "../types";

interface Props {
  memories: Memory[];
  shares: Share[];
  onShare: (paths: string[]) => Promise<string | null>;
  onUnshare: (token: string) => void;
}

export function ShareDialog({ memories, shares, onShare, onUnshare }: Props) {
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [minted, setMinted] = useState<string | null>(null);
  const [refused, setRefused] = useState("");

  const shareable = memories.filter((memory) => !memory.revoked && !memory.sensitive);
  const live = shares.filter((share) => !share.revoked);

  const toggle = (path: string) =>
    setTicked((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  const mint = async () => {
    setRefused("");
    const token = await onShare([...ticked]);
    if (token) {
      setMinted(`${window.location.origin}/s/${token}`);
      setTicked(new Set());
    } else {
      setRefused("That could not be shared.");
    }
  };

  return (
    <details className="fold">
      <summary>
        Hand someone a slice
        {live.length > 0 && <span className="count quiet">{live.length}</span>}
      </summary>
      <div className="card">
        {shareable.length === 0 ? (
          <p className="empty">Nothing here can be shared yet.</p>
        ) : (
          <>
            <div className="candidates">
              {shareable.map((memory) => (
                <label className="tick" key={memory.path}>
                  <input
                    type="checkbox"
                    checked={ticked.has(memory.path)}
                    onChange={() => toggle(memory.path)}
                  />
                  <span className="what">
                    <span className="val">{memory.attested ? "Confirmed only" : memory.value}</span>
                    <span className="meta">
                      <span className="mono">{memory.path}</span> — {memory.note}
                    </span>
                  </span>
                </label>
              ))}
            </div>
            <p className="privacy">
              A special category cannot travel on a link at all, so those are not listed. Links last
              an hour, record every time they are opened, and stop working the moment you revoke
              them or the memory behind them.
            </p>
            <div className="row" style={{ marginTop: 12 }}>
              <button
                className="primary"
                type="button"
                disabled={ticked.size === 0}
                onClick={() => void mint()}
              >
                {ticked.size === 0
                  ? "Pick what to share"
                  : `Make a link to ${ticked.size} ${ticked.size === 1 ? "memory" : "memories"}`}
              </button>
            </div>
          </>
        )}

        {refused && <p className="privacy">{refused}</p>}
        {minted && (
          <p className="privacy" style={{ marginTop: 10 }}>
            <span className="mono">{minted}</span>
          </p>
        )}

        {live.length > 0 && (
          <div style={{ marginTop: 14 }}>
            {live.map((share) => (
              <div className="memory" key={share.token}>
                <div className="note">
                  <span className="value mono">/s/{share.token}</span>
                  <span className="about">
                    {share.paths.join(", ")} · opened {share.views}{" "}
                    {share.views === 1 ? "time" : "times"}
                  </span>
                </div>
                <button className="ghost" type="button" onClick={() => onUnshare(share.token)}>
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
