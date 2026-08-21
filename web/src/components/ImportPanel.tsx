import { useState } from "react";
import type { Candidate } from "../types";

interface Props {
  candidates: Candidate[];
  busy: boolean;
  onExtract: (text: string) => void;
  onKeep: (keep: Candidate[], drop: Candidate[]) => void;
  onCancel: () => void;
}

const PLACEHOLDER = `Anything about you. A few sentences, a bio, a résumé, a memory export from another assistant.

Third-year CS, on exchange in Berlin. Coeliac, so I cook for myself. About 300 euros a month after rent. Freelance frontend — React and TypeScript, learning Rust. Cycle everywhere. I hate phone calls.`;

export function ImportPanel({ candidates, busy, onExtract, onKeep, onCancel }: Props) {
  const [text, setText] = useState("");
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [shown, setShown] = useState<Candidate[]>([]);

  if (candidates.length > 0 && candidates !== shown) {
    setShown(candidates);
    setTicked(new Set(candidates.map((candidate) => candidate.path)));
  }

  const toggle = (path: string) =>
    setTicked((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  if (candidates.length === 0) {
    return (
      <section>
        <h2>Bring your own</h2>
        <div className="card">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={PLACEHOLDER}
            aria-label="Text to read for memories"
            maxLength={20000}
          />
          <p className="privacy">
            This is a public demo. What you paste stays in your session, is never shown to anyone
            else, and is deleted within 24 hours — but do not paste anything you would not hand a
            stranger.
          </p>
          <div className="row" style={{ marginTop: 12 }}>
            <button
              className="primary"
              type="button"
              disabled={busy || text.trim().length < 20}
              onClick={() => onExtract(text)}
            >
              {busy ? "Reading…" : "Read this"}
            </button>
            <button className="ghost" type="button" onClick={onCancel}>
              Back
            </button>
          </div>
        </div>
      </section>
    );
  }

  const keep = candidates.filter((candidate) => ticked.has(candidate.path));
  const drop = candidates.filter((candidate) => !ticked.has(candidate.path));

  return (
    <section>
      <h2>
        Found in what you wrote <span className="count">{candidates.length}</span>
      </h2>
      <div className="card pending">
        <div className="why">nothing is kept until you say so</div>
        <div className="candidates">
          {candidates.map((candidate) => (
            <label className="tick" key={candidate.path}>
              <input
                type="checkbox"
                checked={ticked.has(candidate.path)}
                onChange={() => toggle(candidate.path)}
              />
              <span className="what">
                <span className="val">{candidate.value}</span>
                <span className="meta">
                  <span className="mono">{candidate.path}</span> — {candidate.note}{" "}
                  {candidate.attested && <span className="pill proof">proof only</span>}{" "}
                  {candidate.sensitive && <span className="pill special">special</span>}
                </span>
              </span>
            </label>
          ))}
        </div>
        <div className="row" style={{ marginTop: 14 }}>
          <button
            className="primary"
            type="button"
            disabled={busy}
            onClick={() => onKeep(keep, drop)}
          >
            Keep {keep.length} of {candidates.length}
          </button>
          <button className="ghost" type="button" onClick={onCancel}>
            Discard all
          </button>
        </div>
      </div>
    </section>
  );
}
