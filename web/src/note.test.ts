import { describe, expect, it } from "vitest";
import { asNote, noteName, obsidianUrl } from "./note";
import type { Turn } from "./state";

const turn: Turn = {
  id: 1,
  question: "What should I cook tonight?",
  status: "answered",
  answer: "Microwave khichdi.",
  stamps: [
    {
      path: "kitchen.equipment",
      note: "what I can actually cook with",
      purpose: "so the method fits the room",
      kind: "value",
      reason: "",
    },
    {
      path: "budget.weekly",
      note: "how much I have to spend",
      purpose: "",
      kind: "proof",
      reason: "",
    },
  ],
  cached: false,
  regeneratedWithout: null,
  proposal: null,
  suggestion: null,
  suggestionKept: null,
};

const day = new Date("2026-08-23T10:00:00Z");

describe("an answer on its way out of the app", () => {
  it("carries the receipt for the memories that built it", () => {
    const note = asNote(turn, day);
    expect(note).toContain("Microwave khichdi.");
    expect(note).toContain("2026-08-23");
    expect(note).toContain("`kitchen.equipment` — so the method fits the room");
  });

  it("says an attested memory was confirmed rather than what it held", () => {
    expect(asNote(turn, day)).toContain("`budget.weekly` — how much I have to spend (confirmed");
  });

  it("says so plainly when no memory was handed over", () => {
    expect(asNote({ ...turn, stamps: [] }, day)).toContain("no memories were handed over");
  });

  it("turns a question into a filename a vault will accept", () => {
    expect(noteName("Plan my Saturday: 9am? / 10am")).toBe("Plan my Saturday 9am 10am");
    expect(noteName("///")).toBe("Untitled answer");
  });

  it("puts the whole note inside the obsidian link", () => {
    const url = obsidianUrl(turn, day);
    expect(url.startsWith("obsidian://new?file=Paper%20Trail%2F")).toBe(true);
    expect(decodeURIComponent(url.split("&content=")[1] as string)).toBe(asNote(turn, day));
  });
});
