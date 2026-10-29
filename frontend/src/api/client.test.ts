import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deleteConversation,
  getConversation,
  listConversations,
  stopGeneration,
  streamChat,
  streamRetry,
} from "./client";
import type { StreamEvent } from "./types";

const mockedFetch = vi.fn<typeof fetch>();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sseResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

beforeEach(() => {
  mockedFetch.mockReset();
  vi.stubGlobal("fetch", mockedFetch);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("conversation requests", () => {
  it("lists with a cursor", async () => {
    mockedFetch.mockResolvedValue(jsonResponse({ items: [], next_cursor: null, has_more: false }));

    const page = await listConversations("abc");

    expect(page.items).toEqual([]);
    expect(mockedFetch).toHaveBeenCalledWith("/api/conversations?limit=20&cursor=abc", {
      signal: undefined,
    });
  });

  it("fetches one conversation", async () => {
    mockedFetch.mockResolvedValue(jsonResponse({ id: "c1", messages: [] }));

    await expect(getConversation("c1")).resolves.toMatchObject({ id: "c1" });
    expect(mockedFetch).toHaveBeenCalledWith("/api/conversations/c1", { signal: undefined });
  });

  it("treats a missing conversation on delete as success", async () => {
    mockedFetch.mockResolvedValue(new Response(null, { status: 404 }));

    await expect(deleteConversation("c1")).resolves.toBeUndefined();
  });

  it("throws the API error on a failed delete", async () => {
    mockedFetch.mockResolvedValue(
      jsonResponse({ error: { code: "delete_failed", message: "Nope." } }, 500),
    );

    await expect(deleteConversation("c1")).rejects.toMatchObject({
      code: "delete_failed",
      status: 500,
    });
  });

  it("stops a generation", async () => {
    mockedFetch.mockResolvedValue(new Response(null, { status: 202 }));

    await expect(stopGeneration("c1", "a1")).resolves.toBeUndefined();
    expect(mockedFetch).toHaveBeenCalledWith("/api/conversations/c1/generations/a1/stop", {
      method: "POST",
    });
  });

  it("rejects a failed stop", async () => {
    mockedFetch.mockResolvedValue(
      jsonResponse({ error: { code: "attempt_not_found", message: "Missing." } }, 404),
    );

    await expect(stopGeneration("c1", "a1")).rejects.toMatchObject({
      code: "attempt_not_found",
    });
  });
});

describe("streaming requests", () => {
  it("posts a chat message and yields parsed events", async () => {
    mockedFetch.mockResolvedValue(
      sseResponse([
        'event: meta\ndata: {"conversation_id":"c1","attempt_id":"a1"}\n\n',
        'event: delta\ndata: {"text":"Hi"}\n\n',
      ]),
    );

    const events = await streamChat({ conversationId: null, content: "Hello" });
    const collected: StreamEvent[] = [];
    for await (const event of events) {
      collected.push(event);
    }

    expect(collected).toHaveLength(2);
    expect(collected[1]).toEqual({ type: "delta", data: { text: "Hi" } });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({ method: "POST", body: expect.stringContaining("Hello") }),
    );
  });

  it("retries with the conversation and message ids", async () => {
    mockedFetch.mockResolvedValue(sseResponse([]));

    await streamRetry({ conversationId: "c1", messageId: "m1" });

    expect(mockedFetch).toHaveBeenCalledWith("/api/conversations/c1/messages/m1/retry", {
      method: "POST",
      signal: undefined,
    });
  });

  it("turns an unreadable error body into a generic API error", async () => {
    mockedFetch.mockResolvedValue(new Response("not json", { status: 502 }));

    await expect(streamChat({ conversationId: null, content: "hi" })).rejects.toMatchObject({
      code: "request_failed",
      status: 502,
    });
  });
});
