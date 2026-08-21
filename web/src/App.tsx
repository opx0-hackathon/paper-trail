import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api } from "./api";
import { Flow } from "./components/Flow";
import { McpPanel } from "./components/McpPanel";
import { ImportPanel } from "./components/ImportPanel";
import { Rail } from "./components/Rail";
import { TurnCard } from "./components/TurnCard";
import { initialState, reducer, type Turn } from "./state";
import { remember, stored, system, type Theme } from "./theme";
import type { Candidate, FileState, Stamp, Suggestion } from "./types";
import "./styles/app.css";

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [question, setQuestion] = useState("");
  const [door, setDoor] = useState<"closed" | "import">("closed");
  const [agentToken, setAgentToken] = useState<string | null>(null);
  const nextId = useRef(1);
  const [theme, setTheme] = useState<Theme | null>(stored);
  const [peek, setPeek] = useState(false);

  useEffect(() => {
    api.state().then((file) => dispatch({ type: "file", file }));
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.setAttribute("data-theme", theme);
    else root.removeAttribute("data-theme");
  }, [theme]);

  const showing: Theme = theme ?? system();

  const flipTheme = useCallback(() => {
    setTheme((current) => {
      const next: Theme = (current ?? system()) === "light" ? "dark" : "light";
      remember(next);
      return next;
    });
  }, []);

  const runStream = useCallback(async (id: number, body: Parameters<typeof api.stream>[0]) => {
    let settled = false;
    await api.stream(body, (event) => {
      if (event.name === "stamps") {
        dispatch({ type: "stamps", id, stamps: event.data as Stamp[] });
      } else if (event.name === "token") {
        dispatch({ type: "token", id, text: event.data as string });
      } else if (event.name === "done") {
        const done = event.data as {
          cached: boolean;
          suggestion: Suggestion | null;
        };
        settled = true;
        dispatch({
          type: "answered",
          id,
          answer: "",
          stamps: [],
          cached: done.cached,
          suggestion: done.suggestion,
        });
      } else if (event.name === "state") {
        dispatch({ type: "file", file: event.data as FileState });
      } else if (event.name === "notice") {
        const payload = event.data as { notice?: string };
        dispatch({
          type: "failed",
          id,
          text: payload.notice ?? "That did not go through.",
        });
        settled = true;
      } else if (event.name === "error") {
        dispatch({ type: "failed", id, text: "That did not go through." });
        settled = true;
      }
    });
    if (!settled) {
      dispatch({
        type: "failed",
        id,
        text: "The answer stopped early. Try again.",
      });
    }
  }, []);

  const ask = useCallback(
    async (text: string, without: string | null = null) => {
      const trimmed = text.trim();
      if (!trimmed || state.busy) return;
      const id = nextId.current++;
      dispatch({ type: "start", id, question: trimmed, without });
      dispatch({ type: "began" });
      try {
        if (state.askFirst && without === null) {
          const data = await api.ask(trimmed, true);
          dispatch({ type: "file", file: data });
          if (data.notice) dispatch({ type: "failed", id, text: data.notice });
          else if (data.proposal) dispatch({ type: "asking", id, proposal: data.proposal });
          return;
        }
        await runStream(id, { question: trimmed });
      } catch {
        dispatch({
          type: "failed",
          id,
          text: "That did not go through. Try again in a moment.",
        });
      }
    },
    [state.askFirst, state.busy, runStream],
  );

  const decide = useCallback(
    async (turn: Turn, granted: string[], denied: string[]) => {
      const purposes: Record<string, string> = {};
      for (const item of [...(turn.proposal?.ordinary ?? []), ...(turn.proposal?.special ?? [])]) {
        purposes[item.path] = item.purpose;
      }
      dispatch({
        type: "start",
        id: turn.id,
        question: turn.question,
        without: null,
      });
      try {
        await runStream(turn.id, {
          question: turn.question,
          granted,
          denied,
          purposes,
        });
      } catch {
        dispatch({
          type: "failed",
          id: turn.id,
          text: "That did not go through.",
        });
      }
    },
    [runStream],
  );

  const pull = useCallback(
    async (path: string, forQuestion: string) => {
      const file = await api.revoke(path);
      dispatch({ type: "file", file });
      await ask(forQuestion, path);
    },
    [ask],
  );

  const settleSuggestion = useCallback(
    async (turn: Turn, suggestion: Suggestion, keep: boolean) => {
      const file = keep ? await api.remember(suggestion) : await api.decline(suggestion);
      dispatch({ type: "file", file });
      dispatch({
        type: "suggestionSettled",
        id: turn.id,
        outcome: keep ? "kept" : "declined",
      });
    },
    [],
  );

  const extract = useCallback(async (text: string) => {
    dispatch({ type: "importing", on: true });
    try {
      const data = await api.importText(text);
      dispatch({ type: "file", file: data });
      if (data.notice) dispatch({ type: "notice", text: data.notice });
      dispatch({ type: "candidates", candidates: data.candidates ?? [] });
    } catch {
      dispatch({
        type: "notice",
        text: "Could not read that. Try again in a moment.",
      });
      dispatch({ type: "importing", on: false });
    }
  }, []);

  const keepCandidates = useCallback(async (keep: Candidate[], drop: Candidate[]) => {
    const file = await api.keep(keep, drop);
    dispatch({ type: "file", file });
    dispatch({ type: "clearCandidates" });
    setDoor("closed");
  }, []);

  const connectAgent = useCallback(async () => {
    const data = await api.agent();
    dispatch({ type: "file", file: data });
    setAgentToken(data.token);
  }, []);

  const knock = useCallback(async () => {
    const data = await api.knock();
    dispatch({ type: "file", file: data });
    if (data.notice) dispatch({ type: "notice", text: data.notice });
  }, []);

  const settle = useCallback(async (id: string, paths: string[], standing: boolean) => {
    dispatch({ type: "file", file: await api.settle(id, paths, standing) });
  }, []);

  const ungrant = useCallback(async (id: string) => {
    dispatch({ type: "file", file: await api.ungrant(id) });
  }, []);

  const share = useCallback(async (paths: string[]) => {
    const data = await api.share(paths);
    dispatch({ type: "file", file: data });
    return data.token ?? null;
  }, []);

  const unshare = useCallback(async (token: string) => {
    dispatch({ type: "file", file: await api.unshare(token) });
  }, []);

  const startDemo = useCallback(async () => {
    const file = await api.demo();
    dispatch({ type: "file", file });
    dispatch({ type: "began" });
  }, []);

  const reset = useCallback(async () => {
    const file = await api.restore();
    dispatch({ type: "file", file });
    dispatch({ type: "reset" });
    setDoor("closed");
  }, []);

  const file = state.file;
  const importing = door === "import" || state.candidates.length > 0;
  const held = (file?.memories ?? []).filter((memory) => !memory.revoked).length;
  const empty = state.started && !importing && held === 0;

  const doors = (
    <div className="doors">
      <button className="door primary" type="button" onClick={() => setDoor("import")}>
        <b>Bring your own</b>
        <span>Paste a bio, a résumé, or five sentences. Approve what it keeps.</span>
      </button>
      <button className="door" type="button" onClick={() => void startDemo()}>
        <b>Try a ready-made file</b>
        <span>A student in a hostel room, already filled in. Ask it something.</span>
      </button>
    </div>
  );

  return (
    <>
      <a className="skip" href="#ask">
        Skip to the question box
      </a>

      <header>
        <div className="bar">
          <button
            className="mark"
            type="button"
            onClick={() => setPeek((on) => !on)}
            title={peek ? "Back to your file" : "How it works"}
          >
            <i />
            Paper Trail
          </button>
          <span className="tagline">a memory file that is actually yours</span>
          <span className="status" data-state={file?.live ? "live" : "cached"}>
            <span className="dot" />
            {file?.live ? (file.model ?? "live") : "cached answers"}
          </span>
          <button
            className="theme"
            type="button"
            onClick={flipTheme}
            aria-label={showing === "dark" ? "Switch to light" : "Switch to dark"}
            title={showing === "dark" ? "Switch to light" : "Switch to dark"}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              aria-hidden
            >
              {showing === "dark" ? (
                <>
                  <circle cx="12" cy="12" r="4.2" />
                  <path
                    strokeLinecap="round"
                    d="M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5.4 5.4l1.6 1.6M17 17l1.6 1.6M18.6 5.4L17 7M7 17l-1.6 1.6"
                  />
                </>
              ) : (
                <path
                  strokeLinejoin="round"
                  d="M20.4 14.2A8.6 8.6 0 0 1 9.8 3.6a8.6 8.6 0 1 0 10.6 10.6Z"
                />
              )}
            </svg>
          </button>
        </div>
      </header>

      <main className={(state.started || importing) && !peek ? "working" : ""}>
        <div className="stack">
          {(!state.started || peek) && !importing && (
            <section className="hero">
              <div className="say">
                <span className="eyebrow">every read leaves a receipt</span>
                <h1>
                  Your assistant remembers you. Now you can see <em>exactly</em> what it took.
                </h1>
                <p>
                  Give it anything about yourself and you own a memory file in a minute. Every
                  answer is stamped with the memories it was handed — not what it says it used. Pull
                  one off and it answers again without it.
                </p>
              </div>

              <div className="act">
                {state.started ? (
                  <div className="doors">
                    <button className="door primary" type="button" onClick={() => setPeek(false)}>
                      <b>Back to your file</b>
                      <span>
                        Your memories, the ledger and everything you have granted are still there.
                      </span>
                    </button>
                  </div>
                ) : (
                  doors
                )}

                <ul className="rules">
                  <li>
                    <span>
                      <b>Nothing is read without a receipt.</b> The stamps are written by the code
                      that hands the value over, in the same transaction as the read.
                    </span>
                  </li>
                  <li>
                    <span>
                      <b>Nothing is remembered without being asked.</b> It proposes; you decide.
                    </span>
                  </li>
                  <li>
                    <span>
                      <b>A number can be proved without being told.</b> A budget reaches the model
                      as confirmation, never as a figure.
                    </span>
                  </li>
                </ul>
              </div>
            </section>
          )}

          {(!state.started || peek) && !importing && <Flow />}

          {(!state.started || peek) && !importing && (
            <McpPanel token={agentToken} onConnect={() => void connectAgent()} />
          )}

          {importing && (
            <ImportPanel
              candidates={state.candidates}
              busy={state.importing}
              onExtract={extract}
              onKeep={keepCandidates}
              onCancel={() => {
                dispatch({ type: "clearCandidates" });
                setDoor("closed");
              }}
            />
          )}

          {empty && (
            <section className="hero">
              <div className="say">
                <span className="eyebrow">the file is empty</span>
                <h1>
                  Nothing to hand over, so nothing to <em>stamp</em>.
                </h1>
                <p>
                  Every answer here is built out of the memory file. With an empty one the model has
                  nothing to work from, and the stamp row under the answer would say exactly that.
                  Fill it and ask again.
                </p>
              </div>
              <div className="act">{doors}</div>
            </section>
          )}

          {state.started && !peek && !importing && !empty && (
            <section className="composer" id="ask">
              <div className="starters">
                {(file?.starters ?? []).map((starter) => (
                  <button
                    className="starter"
                    type="button"
                    key={starter}
                    onClick={() => void ask(starter)}
                  >
                    {starter}
                  </button>
                ))}
              </div>
              <form
                className="ask"
                autoComplete="off"
                onSubmit={(event) => {
                  event.preventDefault();
                  void ask(question);
                  setQuestion("");
                }}
              >
                <input
                  type="text"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask it something…"
                  aria-label="Your question"
                  maxLength={400}
                />
                <button className="primary" type="submit" disabled={state.busy}>
                  Ask
                </button>
              </form>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <label className="mode" htmlFor="askfirst">
                  <input
                    type="checkbox"
                    id="askfirst"
                    checked={state.askFirst}
                    onChange={(event) => dispatch({ type: "askFirst", on: event.target.checked })}
                  />
                  <span>
                    <b>Ask me first</b> — show what it wants before it reads
                  </span>
                </label>
                <span className="row">
                  <button
                    className="ghost"
                    type="button"
                    onClick={() => void knock()}
                    title="an assistant elsewhere asks this file for context, over MCP"
                  >
                    Let an assistant elsewhere ask
                  </button>
                  {state.turns.length > 0 && (
                    <button className="ghost" type="button" onClick={() => void reset()}>
                      Start over
                    </button>
                  )}
                </span>
              </div>
            </section>
          )}

          {state.turns.length > 0 && !peek && (
            <section aria-live="polite">
              {state.turns.map((turn) => (
                <TurnCard
                  key={turn.id}
                  turn={turn}
                  busy={state.busy}
                  onPull={(path, forQuestion) => void pull(path, forQuestion)}
                  onDecide={(target, granted, denied) => void decide(target, granted, denied)}
                  onSuggestion={(target, suggestion, keep) =>
                    void settleSuggestion(target, suggestion, keep)
                  }
                />
              ))}
            </section>
          )}

          {state.notice && <div className="card notice">{state.notice}</div>}
        </div>

        {(state.started || importing) && !peek && file && (
          <Rail
            file={file}
            agentToken={agentToken}
            exportUrl={api.exportUrl}
            onConnect={() => void connectAgent()}
            onKnock={() => void knock()}
            onSettle={(id, paths, standing) => void settle(id, paths, standing)}
            onUngrant={(id) => void ungrant(id)}
            onShare={share}
            onUnshare={(token) => void unshare(token)}
          />
        )}
      </main>

      <footer>
        <span>Paper Trail</span>
        <a href="https://github.com/opx0/paper-trail">Source, MIT</a>
        <a href="https://github.com/opx0/paper-trail/blob/main/docs/MCP.md">MCP</a>
        <button className="ghost link" type="button" onClick={() => setPeek(true)}>
          How it works
        </button>
        <span>A governed memory file</span>
      </footer>
    </>
  );
}
