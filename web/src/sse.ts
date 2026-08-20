export interface ServerEvent {
  name: string;
  data: unknown;
}

/**
 * Reassembles server-sent events from chunks that may split anywhere, including
 * mid-field and mid-multibyte-character.
 */
export function createSseParser() {
  let buffer = "";

  return function push(chunk: string): ServerEvent[] {
    buffer += chunk;
    const events: ServerEvent[] = [];
    let boundary = buffer.indexOf("\n\n");

    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = parseBlock(block);
      if (event) events.push(event);
      boundary = buffer.indexOf("\n\n");
    }

    return events;
  };
}

function parseBlock(block: string): ServerEvent | null {
  let name = "message";
  const data: string[] = [];

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }

  if (data.length === 0) return null;
  try {
    return { name, data: JSON.parse(data.join("\n")) };
  } catch {
    return null;
  }
}

export async function readEvents(
  response: Response,
  onEvent: (event: ServerEvent) => void,
): Promise<void> {
  const body = response.body;
  if (!body) throw new Error("no stream on the response");

  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  const push = createSseParser();

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const event of push(value)) onEvent(event);
  }
}
