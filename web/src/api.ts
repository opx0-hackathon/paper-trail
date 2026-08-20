import { readEvents, type ServerEvent } from "./sse";
import type { AnswerPayload, Candidate, FileState, ImportPayload, ProposalPayload } from "./types";

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok && response.status !== 400) {
    throw new Error(`${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  state: async (): Promise<FileState> => {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error("could not load the memory file");
    return (await response.json()) as FileState;
  },

  stream: async (
    body: {
      question: string;
      granted?: string[];
      denied?: string[];
      purposes?: Record<string, string>;
    },
    onEvent: (event: ServerEvent) => void,
  ): Promise<void> => {
    const response = await fetch("/api/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`stream failed with ${response.status}`);
    if (!response.headers.get("content-type")?.includes("event-stream")) {
      onEvent({ name: "notice", data: await response.json() });
      return;
    }
    await readEvents(response, onEvent);
  },

  ask: (question: string, askFirst: boolean) =>
    post<AnswerPayload & Partial<ProposalPayload>>("/api/ask", {
      question,
      mode: askFirst ? "ask" : "auto",
    }),

  answer: (
    question: string,
    granted: string[],
    denied: string[],
    purposes: Record<string, string>,
  ) => post<AnswerPayload>("/api/answer", { question, granted, denied, purposes }),

  revoke: (path: string) => post<FileState>("/api/revoke", { path }),

  restore: () => post<FileState>("/api/restore", {}),

  demo: () => post<FileState>("/api/demo", {}),

  remember: (suggestion: { path: string; value: string; note: string }) =>
    post<FileState>("/api/remember", suggestion),

  decline: (suggestion: { path: string; value: string }) =>
    post<FileState>("/api/decline", suggestion),

  importText: (text: string) => post<ImportPayload>("/api/import", { text }),

  keep: (keep: Candidate[], drop: Candidate[]) =>
    post<FileState & { kept: number }>("/api/keep", { keep, drop }),

  share: (paths: string[]) =>
    post<FileState & { token?: string; code?: string }>("/api/share", { paths }),

  unshare: (token: string) => post<FileState>("/api/unshare", { token }),

  agent: () => post<FileState & { token: string }>("/api/agent", {}),

  knock: () => post<FileState & { notice?: string }>("/api/knock", {}),

  settle: (id: string, paths: string[], standing: boolean) =>
    post<FileState>("/api/settle", { id, paths, standing }),

  ungrant: (id: string) => post<FileState>("/api/ungrant", { id }),

  exportUrl: (format: "json" | "markdown") => `/api/export?format=${format}`,
};
