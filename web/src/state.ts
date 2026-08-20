import type { Candidate, FileState, Proposal, Stamp, Suggestion } from "./types";

export interface Turn {
  id: number;
  question: string;
  status: "thinking" | "asking" | "streaming" | "answered" | "failed";
  answer: string;
  stamps: Stamp[];
  cached: boolean;
  regeneratedWithout: string | null;
  proposal: Proposal | null;
  suggestion: Suggestion | null;
  suggestionKept: "kept" | "declined" | null;
}

export interface AppState {
  file: FileState | null;
  turns: Turn[];
  candidates: Candidate[];
  askFirst: boolean;
  busy: boolean;
  notice: string;
  importing: boolean;
  started: boolean;
}

export type Action =
  | { type: "file"; file: FileState }
  | { type: "askFirst"; on: boolean }
  | { type: "notice"; text: string }
  | { type: "start"; id: number; question: string; without: string | null }
  | { type: "asking"; id: number; proposal: Proposal }
  | { type: "stamps"; id: number; stamps: Stamp[] }
  | { type: "token"; id: number; text: string }
  | {
      type: "answered";
      id: number;
      answer: string;
      stamps: Stamp[];
      cached: boolean;
      suggestion: Suggestion | null;
    }
  | { type: "failed"; id: number; text: string }
  | { type: "suggestionSettled"; id: number; outcome: "kept" | "declined" }
  | { type: "candidates"; candidates: Candidate[] }
  | { type: "clearCandidates" }
  | { type: "importing"; on: boolean }
  | { type: "began" }
  | { type: "reset" };

export const initialState: AppState = {
  file: null,
  turns: [],
  candidates: [],
  askFirst: false,
  busy: false,
  notice: "",
  importing: false,
  started: false,
};

function patch(state: AppState, id: number, change: Partial<Turn>): Turn[] {
  return state.turns.map((turn) => (turn.id === id ? { ...turn, ...change } : turn));
}

function anyPending(turns: Turn[]): boolean {
  return turns.some((turn) => turn.status === "thinking" || turn.status === "streaming");
}

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "file":
      return { ...state, file: action.file };

    case "askFirst":
      return { ...state, askFirst: action.on };

    case "notice":
      return { ...state, notice: action.text, busy: false };

    case "start": {
      const turn: Turn = {
        id: action.id,
        question: action.question,
        status: "thinking",
        answer: "",
        stamps: [],
        cached: false,
        regeneratedWithout: action.without,
        proposal: null,
        suggestion: null,
        suggestionKept: null,
      };
      return { ...state, turns: [turn, ...state.turns], busy: true, notice: "" };
    }

    case "asking": {
      const turns = patch(state, action.id, { status: "asking", proposal: action.proposal });
      return { ...state, turns, busy: anyPending(turns) };
    }

    case "stamps": {
      const turns = patch(state, action.id, { status: "streaming", stamps: action.stamps });
      return { ...state, turns };
    }

    case "token": {
      const current = state.turns.find((turn) => turn.id === action.id);
      const turns = patch(state, action.id, {
        status: "streaming",
        answer: (current?.answer ?? "") + action.text,
      });
      return { ...state, turns };
    }

    case "answered": {
      const current = state.turns.find((turn) => turn.id === action.id);
      const turns = patch(state, action.id, {
        status: "answered",
        answer: action.answer || current?.answer || "",
        stamps: action.stamps.length ? action.stamps : (current?.stamps ?? []),
        cached: action.cached,
        suggestion: action.suggestion,
        proposal: null,
      });
      return { ...state, turns, busy: anyPending(turns) };
    }

    case "failed": {
      const turns = patch(state, action.id, { status: "failed", answer: action.text });
      return { ...state, turns, busy: anyPending(turns) };
    }

    case "suggestionSettled":
      return { ...state, turns: patch(state, action.id, { suggestionKept: action.outcome }) };

    case "candidates":
      return { ...state, candidates: action.candidates, importing: false, started: true };

    case "clearCandidates":
      return { ...state, candidates: [] };

    case "importing":
      return { ...state, importing: action.on, notice: "" };

    case "began":
      return { ...state, started: true };

    case "reset":
      return { ...state, turns: [], candidates: [], notice: "", busy: false, started: false };

    default:
      return state;
  }
}
