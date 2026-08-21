import { useState } from "react";
import { ApprovalCard } from "./ApprovalCard";
import { StampRow } from "./StampRow";
import { asNote, obsidianUrl } from "../note";
import type { Turn } from "../state";
import type { Suggestion } from "../types";

interface Props {
  turn: Turn;
  busy: boolean;
  onPull: (path: string, question: string) => void;
  onDecide: (turn: Turn, granted: string[], denied: string[]) => void;
  onSuggestion: (turn: Turn, suggestion: Suggestion, keep: boolean) => void;
}

export function TurnCard({ turn, busy, onPull, onDecide, onSuggestion }: Props) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(asNote(turn));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  if (turn.status === "asking" && turn.proposal) {
    return (
      <ApprovalCard
        proposal={turn.proposal}
        onDecide={(granted, denied) => onDecide(turn, granted, denied)}
      />
    );
  }

  return (
    <div className={`card turn${turn.status === "failed" ? " notice" : ""}`}>
      <div className="question">
        <span className="caret">&rsaquo;</span>
        {turn.question}
      </div>

      {turn.regeneratedWithout && (
        <div className="regen">answered again without {turn.regeneratedWithout}</div>
      )}

      {turn.status === "thinking" ? (
        <div className="answer thinking">
          <i />
          deciding which memories it needs…
        </div>
      ) : (
        <div className="answer">
          {turn.answer}
          {turn.status === "streaming" && <span className="cursor" />}
        </div>
      )}

      {(turn.status === "answered" || turn.status === "streaming") && (
        <>
          <div className="handed">
            <div className="label">handed to the model{turn.cached ? " · cached answer" : ""}</div>
            <StampRow
              stamps={turn.stamps}
              revokedPath={turn.regeneratedWithout}
              busy={busy}
              onPull={(path) => onPull(path, turn.question)}
            />
          </div>

          {turn.status === "answered" && turn.answer.trim() !== "" && (
            <div className="takeaway">
              <div className="label">keep the answer, with its receipt</div>
              <div className="row">
                <button
                  className="ghost"
                  type="button"
                  onClick={() => {
                    window.location.href = obsidianUrl(turn);
                  }}
                >
                  Send to Obsidian
                </button>
                <button className="ghost" type="button" onClick={() => void copy()}>
                  {copied ? "Copied" : "Copy as Markdown"}
                </button>
              </div>
            </div>
          )}

          {turn.suggestion && (
            <div className="keep">
              <div className="head">the assistant would like to remember this</div>
              <div className="fact">
                {turn.suggestion.value}
                <span className="as">
                  {turn.suggestion.path} — {turn.suggestion.note}
                </span>
              </div>
              {turn.suggestionKept === null ? (
                <div className="row">
                  <button
                    className="yes"
                    type="button"
                    onClick={() => onSuggestion(turn, turn.suggestion as Suggestion, true)}
                  >
                    Keep it
                  </button>
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => onSuggestion(turn, turn.suggestion as Suggestion, false)}
                  >
                    Don&rsquo;t
                  </button>
                </div>
              ) : (
                <div className="kept">
                  {turn.suggestionKept === "kept"
                    ? "Kept. It is in the memory file, and on the ledger."
                    : "Not kept — and the ledger says it was asked for."}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
