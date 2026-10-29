/**
 * Server-Sent Events parser for the chat stream.
 *
 * The API sends one named event per frame with a single JSON data line. We parse
 * defensively: frames may be split across chunks, use CRLF, include comment
 * heartbeats, or carry events this client does not know about.
 */

import type { StreamEvent } from "./types";

const KNOWN_EVENTS = new Set(["meta", "delta", "usage", "done", "error"]);

export async function* parseSseFrames(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<StreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseFrame(frame);
        if (event) {
          yield event;
        }
        boundary = buffer.indexOf("\n\n");
      }
    }

    buffer += decoder.decode();
    const trailing = parseFrame(buffer);
    if (trailing) {
      yield trailing;
    }
  } finally {
    reader.releaseLock();
  }
}

export function parseFrame(raw: string): StreamEvent | null {
  let name = "";
  const data: string[] = [];

  for (const line of raw.split("\n")) {
    const trimmed = line.endsWith("\r") ? line.slice(0, -1) : line;
    if (!trimmed || trimmed.startsWith(":")) {
      continue;
    }
    if (trimmed.startsWith("event:")) {
      name = trimmed.slice("event:".length).trim();
    } else if (trimmed.startsWith("data:")) {
      data.push(trimmed.slice("data:".length).replace(/^ /, ""));
    }
  }

  if (!name || data.length === 0 || !KNOWN_EVENTS.has(name)) {
    return null;
  }

  return { type: name, data: JSON.parse(data.join("\n")) } as StreamEvent;
}
