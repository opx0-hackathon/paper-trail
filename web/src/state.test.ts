import { describe, expect, it } from "vitest";
import { initialState, reducer, type AppState } from "./state";
import type { Proposal, Stamp } from "./types";

const stamp = (path: string): Stamp => ({
  path,
  note: "",
  purpose: "",
  kind: "value",
  reason: "",
});

const proposal: Proposal = {
  question: "What should I cook tonight?",
  ordinary: [{ path: "diet.style", note: "what I eat", purpose: "restrictions", sensitive: false }],
  special: [{ path: "health.condition", note: "a condition", purpose: "safety", sensitive: true }],
  cached: false,
};

const started = (): AppState =>
  reducer(initialState, {
    type: "start",
    id: 1,
    question: "What should I cook tonight?",
    without: null,
  });

describe("reducer", () => {
  it("marks the app busy while a turn is in flight and free once it lands", () => {
    const asking = started();
    expect(asking.busy).toBe(true);
    const done = reducer(asking, {
      type: "answered",
      id: 1,
      answer: "Khichdi.",
      stamps: [stamp("diet.style")],
      cached: false,
      suggestion: null,
    });
    expect(done.busy).toBe(false);
    expect(done.turns[0]?.answer).toBe("Khichdi.");
  });

  it("keeps the newest turn first", () => {
    const first = started();
    const second = reducer(first, {
      type: "start",
      id: 2,
      question: "Plan my Saturday.",
      without: null,
    });
    expect(second.turns.map((turn) => turn.id)).toEqual([2, 1]);
  });

  it("remembers which memory a regenerated turn was answered without", () => {
    const again = reducer(started(), {
      type: "start",
      id: 2,
      question: "What should I cook tonight?",
      without: "kitchen.equipment",
    });
    expect(again.turns[0]?.regeneratedWithout).toBe("kitchen.equipment");
  });

  it("stays busy while one of several turns is still thinking", () => {
    const two = reducer(started(), {
      type: "start",
      id: 2,
      question: "Plan my Saturday.",
      without: null,
    });
    const one = reducer(two, {
      type: "answered",
      id: 2,
      answer: "Cubbon Park.",
      stamps: [],
      cached: false,
      suggestion: null,
    });
    expect(one.busy).toBe(true);
  });

  it("holds a proposal without answering, so consent has somewhere to happen", () => {
    const asking = reducer(started(), { type: "asking", id: 1, proposal });
    expect(asking.turns[0]?.status).toBe("asking");
    expect(asking.turns[0]?.answer).toBe("");
    expect(asking.turns[0]?.proposal?.special).toHaveLength(1);
  });

  it("clears the proposal once the turn is answered", () => {
    const asking = reducer(started(), { type: "asking", id: 1, proposal });
    const answered = reducer(asking, {
      type: "answered",
      id: 1,
      answer: "Khichdi.",
      stamps: [],
      cached: false,
      suggestion: null,
    });
    expect(answered.turns[0]?.proposal).toBeNull();
  });

  it("records a suggestion outcome without touching the answer", () => {
    const answered = reducer(started(), {
      type: "answered",
      id: 1,
      answer: "Khichdi.",
      stamps: [],
      cached: false,
      suggestion: { path: "routine.gym", value: "Tue and Thu.", note: "when I exercise" },
    });
    const kept = reducer(answered, { type: "suggestionSettled", id: 1, outcome: "kept" });
    expect(kept.turns[0]?.suggestionKept).toBe("kept");
    expect(kept.turns[0]?.answer).toBe("Khichdi.");
  });

  it("a notice frees the app so a rate limit cannot wedge the form", () => {
    const limited = reducer(started(), { type: "notice", text: "This desk is busy." });
    expect(limited.busy).toBe(false);
    expect(limited.notice).toBe("This desk is busy.");
  });

  it("reset clears turns and candidates but keeps the loaded file", () => {
    const withFile = reducer(started(), {
      type: "file",
      file: {
        holder: "Arjun",
        starters: [],
        live: true,
        model: "m",
        memories: [],
        receipts: [],
        shares: [],
        grants: [],
        pending: [],
      },
    });
    const cleared = reducer(withFile, { type: "reset" });
    expect(cleared.turns).toHaveLength(0);
    expect(cleared.file?.holder).toBe("Arjun");
  });
});
