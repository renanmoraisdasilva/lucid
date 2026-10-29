import { describe, expect, it } from "vitest";

import { parseSseFrames } from "./sse";
import type { StreamEvent } from "./types";

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

async function collect(chunks: string[]): Promise<StreamEvent[]> {
  const events: StreamEvent[] = [];
  for await (const event of parseSseFrames(streamOf(chunks))) {
    events.push(event);
  }
  return events;
}

const META =
  'event: meta\ndata: {"conversation_id":"c1","conversation_title":"T","user_message_id":"u1","attempt_id":"a1","model":"m","is_new_conversation":true}\n\n';
const DELTA = 'event: delta\ndata: {"text":"Hello"}\n\n';
const DONE =
  'event: done\ndata: {"attempt_id":"a1","status":"completed","assistant_message_id":"m1","finish_reason":"stop"}\n\n';

describe("parseSseFrames", () => {
  it("parses named events in order", async () => {
    const events = await collect([META, DELTA, DONE]);

    expect(events.map((event) => event.type)).toEqual(["meta", "delta", "done"]);
    expect(events[1]).toEqual({ type: "delta", data: { text: "Hello" } });
  });

  it("reassembles a frame split across chunks", async () => {
    const events = await collect([META.slice(0, 20), META.slice(20, 60), META.slice(60)]);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("meta");
  });

  it("handles CRLF line endings", async () => {
    const crlf = 'event: delta\r\ndata: {"text":"x"}\r\n\r\n';

    const events = await collect([crlf]);

    expect(events).toEqual([{ type: "delta", data: { text: "x" } }]);
  });

  it("ignores comment heartbeats", async () => {
    const events = await collect([": ping\n\n", DELTA]);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("delta");
  });

  it("ignores unknown event names", async () => {
    const events = await collect(['event: mystery\ndata: {"x":1}\n\n', DELTA]);

    expect(events.map((event) => event.type)).toEqual(["delta"]);
  });

  it("emits a trailing frame without a final blank line", async () => {
    const events = await collect(['event: delta\ndata: {"text":"tail"}']);

    expect(events).toEqual([{ type: "delta", data: { text: "tail" } }]);
  });

  it("carries the terminal status through", async () => {
    const events = await collect([DONE]);
    const done = events[0];

    expect(done.type).toBe("done");
    if (done.type === "done") {
      expect(done.data.status).toBe("completed");
      expect(done.data.assistant_message_id).toBe("m1");
    }
  });
});
