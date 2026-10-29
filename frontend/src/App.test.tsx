import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const CONVERSATION_ID = "0192f3c1-0000-7000-8000-000000000001";
const USER_MESSAGE_ID = "0192f3c1-0000-7000-8000-000000000002";

const conversationSummary = {
  id: CONVERSATION_ID,
  title: "Hello Lucid",
  created_at: "2026-10-29T10:42:00Z",
  updated_at: "2026-10-29T10:42:01Z",
  active_attempt_id: null,
};

const conversationDetail = {
  ...conversationSummary,
  messages: [
    {
      id: USER_MESSAGE_ID,
      role: "user",
      seq: 1,
      content: "Hello Lucid",
      created_at: "2026-10-29T10:42:00Z",
      attempt: {
        id: "a1",
        status: "completed",
        model: "fake-model",
        attempt_no: 1,
        retryable: false,
        error_code: null,
        usage: null,
      },
    },
    {
      id: "0192f3c1-0000-7000-8000-000000000003",
      role: "assistant",
      seq: 2,
      content: "Hello! How can I help?",
      created_at: "2026-10-29T10:42:01Z",
      attempt: {
        id: "a1",
        status: "completed",
        model: "fake-model",
        attempt_no: 1,
        retryable: false,
        error_code: null,
        usage: { input_tokens: 11, output_tokens: 7, thought_tokens: 0, total_tokens: 18 },
      },
    },
  ],
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
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

function installFetchMock(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();

      if (url === "/api/chat") {
        return sseResponse([
          `event: meta\ndata: ${JSON.stringify({
            conversation_id: CONVERSATION_ID,
            conversation_title: "Hello Lucid",
            user_message_id: USER_MESSAGE_ID,
            attempt_id: "a1",
            model: "fake-model",
            is_new_conversation: true,
          })}\n\n`,
          'event: delta\ndata: {"text":"Hello! "}\n\n',
          'event: delta\ndata: {"text":"How can I help?"}\n\n',
          'event: usage\ndata: {"input_tokens":11,"output_tokens":7,"thought_tokens":0,"total_tokens":18}\n\n',
          'event: done\ndata: {"attempt_id":"a1","status":"completed","assistant_message_id":"m1","finish_reason":"stop"}\n\n',
        ]);
      }
      if (url === "/api/conversations") {
        return jsonResponse({ items: [conversationSummary], next_cursor: null, has_more: false });
      }
      if (url === `/api/conversations/${CONVERSATION_ID}`) {
        return jsonResponse(conversationDetail);
      }
      throw new Error(`Unexpected request: ${url}`);
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows the empty state and the loaded conversations", async () => {
    installFetchMock();

    render(<App />);

    expect(screen.getByRole("heading", { name: "How can Lucid help today?" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Hello Lucid" })).toBeInTheDocument();
  });

  it("streams a reply, then shows the persisted conversation", async () => {
    installFetchMock();
    const user = userEvent.setup();

    render(<App />);

    await user.type(screen.getByLabelText("Message Lucid"), "Hello Lucid{Enter}");

    expect(await screen.findByText("Hello! How can I help?")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Message Lucid")).not.toBeDisabled();
    });
  });

  it("disables the composer while a response is streaming", async () => {
    const gate = { close: () => {} };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/chat") {
          const encoder = new TextEncoder();
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(
                encoder.encode(
                  `event: meta\ndata: ${JSON.stringify({
                    conversation_id: CONVERSATION_ID,
                    conversation_title: "Hello Lucid",
                    user_message_id: USER_MESSAGE_ID,
                    attempt_id: "a1",
                    model: "fake-model",
                    is_new_conversation: true,
                  })}\n\n`,
                ),
              );
              controller.enqueue(encoder.encode('event: delta\ndata: {"text":"thinking"}\n\n'));
              gate.close = () => controller.close();
            },
          });
          return new Response(body, {
            status: 200,
            headers: { "Content-Type": "text/event-stream" },
          });
        }
        if (url === "/api/conversations") {
          return jsonResponse({ items: [], next_cursor: null, has_more: false });
        }
        if (url === `/api/conversations/${CONVERSATION_ID}`) {
          return jsonResponse({ ...conversationDetail, messages: [] });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );
    const user = userEvent.setup();

    render(<App />);

    await user.type(screen.getByLabelText("Message Lucid"), "Hello Lucid{Enter}");

    expect(await screen.findByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(screen.getByLabelText("Message Lucid")).toBeDisabled();

    gate.close();
    await waitFor(() => {
      expect(screen.getByLabelText("Message Lucid")).not.toBeDisabled();
    });
  });
});
