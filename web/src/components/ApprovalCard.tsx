import { useState } from "react";
import type { Ask, Proposal } from "../types";

interface Props {
  proposal: Proposal;
  onDecide: (granted: string[], denied: string[]) => void;
}

export function ApprovalCard({ proposal, onDecide }: Props) {
  const [ticked, setTicked] = useState<Set<string>>(
    () => new Set(proposal.ordinary.map((ask) => ask.path)),
  );

  const toggle = (path: string) =>
    setTicked((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });

  const every = [...proposal.ordinary, ...proposal.special].map((ask) => ask.path);
  const decide = (granted: string[]) =>
    onDecide(
      granted,
      every.filter((path) => !granted.includes(path)),
    );

  const row = (ask: Ask) => (
    <label className="tick" key={ask.path}>
      <input type="checkbox" checked={ticked.has(ask.path)} onChange={() => toggle(ask.path)} />
      <span className="what">
        <span className="mem mono">{ask.path}</span>
        <span className="why-line">
          {ask.note} — <b>{ask.purpose || "no reason given"}</b>
        </span>
      </span>
    </label>
  );

  return (
    <div className="card turn pending">
      <div className="why">the model is asking</div>
      <div className="question" style={{ marginTop: 4 }}>
        <span className="caret">&rsaquo;</span>
        {proposal.question}
      </div>

      <div className="grant">{proposal.ordinary.map(row)}</div>

      {proposal.special.length > 0 && (
        <div className="apart">
          <div className="head">asked for separately</div>
          <div className="rule">
            A special category does not ride along with ordinary preferences. It travels as its own
            request, or not at all — so this one starts unticked.
          </div>
          {proposal.special.map(row)}
        </div>
      )}

      <div className="row" style={{ marginTop: 14 }}>
        <button className="primary" type="button" onClick={() => decide([...ticked])}>
          Hand over what&rsquo;s ticked
        </button>
        <button className="ghost" type="button" onClick={() => decide([])}>
          Refuse everything
        </button>
      </div>
    </div>
  );
}
