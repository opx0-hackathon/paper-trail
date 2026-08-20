import type { Turn } from "./state";
import type { Stamp } from "./types";

const stampLine = (stamp: Stamp): string => {
  if (stamp.kind === "proof")
    return `- \`${stamp.path}\` — ${stamp.note} (confirmed only, the value never left)`;
  if (stamp.kind === "refused") return `- \`${stamp.path}\` — refused: ${stamp.reason}`;
  return `- \`${stamp.path}\` — ${stamp.purpose || stamp.note}`;
};

/** A filename Obsidian will accept, without the characters that break a vault path. */
export function noteName(question: string): string {
  const clean = question
    .replace(/[\\/:*?"<>|#^[\]]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 60)
    .trim();
  return clean || "Untitled answer";
}

/** The answer, and underneath it the receipt for what built the answer. */
export function asNote(turn: Turn, now: Date = new Date()): string {
  const when = now.toISOString().slice(0, 10);
  const lines = [`# ${turn.question}`, "", turn.answer.trim(), "", "---", ""];
  if (turn.stamps.length === 0) {
    lines.push(`_Paper Trail · ${when} · no memories were handed over._`);
  } else {
    lines.push(`_Paper Trail · ${when} · built from:_`, "");
    lines.push(...turn.stamps.map(stampLine));
  }
  return lines.join("\n") + "\n";
}

/**
 * Opens Obsidian on the last-used vault and drops the note in a Paper Trail folder.
 * ponytail: URI carries the content, so a very long answer can hit the browser's URL
 * cap. Copy as Markdown is the escape hatch; move to the local REST plugin if it bites.
 */
export function obsidianUrl(turn: Turn, now?: Date): string {
  const file = encodeURIComponent(`Paper Trail/${noteName(turn.question)}`);
  const content = encodeURIComponent(asNote(turn, now));
  return `obsidian://new?file=${file}&content=${content}`;
}
