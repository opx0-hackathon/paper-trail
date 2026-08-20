import { describe, expect, it } from "vitest";
import { createSseParser } from "./sse";

describe("sse parser", () => {
  it("reads a whole event from one chunk", () => {
    const push = createSseParser();
    expect(push('event: token\ndata: "hi"\n\n')).toEqual([{ name: "token", data: "hi" }]);
  });

  it("reassembles an event split across chunks", () => {
    const push = createSseParser();
    expect(push("event: tok")).toEqual([]);
    expect(push('en\ndata: "hi')).toEqual([]);
    expect(push('"\n\n')).toEqual([{ name: "token", data: "hi" }]);
  });

  it("reads several events out of one chunk", () => {
    const push = createSseParser();
    const events = push('event: token\ndata: "a"\n\nevent: token\ndata: "b"\n\n');
    expect(events.map((event) => event.data)).toEqual(["a", "b"]);
  });

  it("keeps a trailing partial event until its terminator arrives", () => {
    const push = createSseParser();
    expect(push('event: token\ndata: "a"\n\nevent: token\ndata: "b"')).toHaveLength(1);
    expect(push("\n\n")).toEqual([{ name: "token", data: "b" }]);
  });

  it("parses structured payloads", () => {
    const push = createSseParser();
    const [event] = push('event: stamps\ndata: [{"path":"diet.style","kind":"value"}]\n\n');
    expect(event?.name).toBe("stamps");
    expect(event?.data).toEqual([{ path: "diet.style", kind: "value" }]);
  });

  it("joins a payload split across several data fields", () => {
    const push = createSseParser();
    const [event] = push('event: done\ndata: {\ndata:   "cached": false\ndata: }\n\n');
    expect(event?.data).toEqual({ cached: false });
  });

  it("keeps escaped newlines inside a token intact", () => {
    const push = createSseParser();
    const [event] = push('event: token\ndata: "line one\\nline two"\n\n');
    expect(event?.data).toBe("line one\nline two");
  });

  it("drops a block whose payload is not JSON rather than throwing", () => {
    const push = createSseParser();
    expect(push("event: token\ndata: not json\n\n")).toEqual([]);
  });

  it("ignores a comment-only keepalive block", () => {
    const push = createSseParser();
    expect(push(": keepalive\n\n")).toEqual([]);
  });

  it("survives a token that is an empty string", () => {
    const push = createSseParser();
    expect(push('event: token\ndata: ""\n\n')).toEqual([{ name: "token", data: "" }]);
  });
});
