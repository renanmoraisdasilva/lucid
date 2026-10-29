import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { dashboardData } from "./test/fixtures/dashboard";

const CONVERSATION_ID = "0192f3c1-0000-7000-8000-000000000001";
const USER_MESSAGE_ID = "0192f3c1-0000-7000-8000-000000000002";

const conversationSummary = {
  id: CONVERSATION_ID,
  title: "Hello Lucid",
  created_at: "2026-10-29T10:42:00Z",
  updated_at: new Date().toISOString(),
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
        error_message: null,
        usage: null,
      },
    },
    {
      id: "0192f3c1-0000-7000-8000-000000000003",
      role: "assistant",
      seq: 2,
      content: "## Hello!\n\nHow can I help?",
      created_at: "2026-10-29T10:42:01Z",
      attempt: {
        id: "a1",
        status: "completed",
        model: "fake-model",
        attempt_no: 1,
        retryable: false,
        error_code: null,
        error_message: null,
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

function metaFrame(): string {
  return `event: meta\ndata: ${JSON.stringify({
    conversation_id: CONVERSATION_ID,
    conversation_title: "Hello Lucid",
    user_message_id: USER_MESSAGE_ID,
    attempt_id: "a1",
    model: "fake-model",
    is_new_conversation: true,
  })}\n\n`;
}

const GROQ_MODEL_ID = "openai:openai/gpt-oss-120b";
const GEMINI_MODEL_ID = "gemini:gemini-3.6-flash";

function modelsResponse(): Response {
  return jsonResponse({
    items: [
      {
        id: GROQ_MODEL_ID,
        label: "openai/gpt-oss-120b \u00b7 Groq",
        provider: "openai",
        model: "openai/gpt-oss-120b",
      },
      {
        id: GEMINI_MODEL_ID,
        label: "gemini-3.6-flash \u00b7 Gemini",
        provider: "gemini",
        model: "gemini-3.6-flash",
      },
    ],
    default_id: GROQ_MODEL_ID,
  });
}

function modelPicker(): HTMLElement {
  return screen.getByRole("button", { name: /^Model: / });
}

function chatBodies(init?: RequestInit): Record<string, unknown> {
  return JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
}

function installFetchMock(sent: Record<string, unknown>[] = []): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";

      if (url === "/api/models") {
        return modelsResponse();
      }
      if (url === "/api/chat") {
        sent.push(chatBodies(init));
        return sseResponse([
          metaFrame(),
          'event: delta\ndata: {"text":"## Hello!\\n\\nHow can I help?"}\n\n',
          'event: usage\ndata: {"input_tokens":11,"output_tokens":7,"thought_tokens":0,"total_tokens":18}\n\n',
          'event: done\ndata: {"attempt_id":"a1","status":"completed","assistant_message_id":"m1","finish_reason":"stop"}\n\n',
        ]);
      }
      if (url.startsWith("/api/dashboard?")) {
        return jsonResponse(dashboardData());
      }
      if (url.startsWith("/api/conversations?")) {
        return jsonResponse({ items: [conversationSummary], next_cursor: null, has_more: false });
      }
      if (url === `/api/conversations/${CONVERSATION_ID}` && method === "DELETE") {
        return new Response(null, { status: 204 });
      }
      if (url === `/api/conversations/${CONVERSATION_ID}`) {
        return jsonResponse(conversationDetail);
      }
      throw new Error(`Unexpected request: ${method} ${url}`);
    }),
  );
}

function renderApp({ strict = false }: { strict?: boolean } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  const tree = (
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  );
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("App", () => {
  it("shows the empty state and the loaded conversations", async () => {
    installFetchMock();

    renderApp();

    expect(screen.getByRole("heading", { name: "How can Lucid help today?" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Hello Lucid" })).toBeInTheDocument();
  });

  it("streams a reply, then renders the persisted Markdown", async () => {
    installFetchMock();
    const user = userEvent.setup();

    renderApp();

    await user.type(screen.getByLabelText("Message Lucid"), "Hello Lucid{Enter}");

    expect(await screen.findByRole("heading", { name: "Hello!" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Message Lucid")).not.toBeDisabled();
    });
  });

  it("sends the selected model with the message", async () => {
    const sent: Record<string, unknown>[] = [];
    installFetchMock(sent);
    const user = userEvent.setup();

    renderApp();

    const picker = await screen.findByRole("button", { name: /^Model: / });
    expect(picker).toHaveTextContent("openai/gpt-oss-120b");

    await user.click(picker);
    expect(screen.getByRole("listbox", { name: "Model" })).toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /gemini-3\.6-flash/ }));

    expect(screen.queryByRole("listbox")).toBeNull();
    expect(picker).toHaveTextContent("gemini-3.6-flash");

    await user.type(screen.getByLabelText("Message Lucid"), "Hello Lucid{Enter}");

    await waitFor(() => {
      expect(sent).toHaveLength(1);
    });
    expect(sent[0]).toMatchObject({ content: "Hello Lucid", model_id: GEMINI_MODEL_ID });
  });

  it("returns to idle after the stream ends when StrictMode remounts effects", async () => {
    installFetchMock();
    const user = userEvent.setup();

    renderApp({ strict: true });

    await user.type(screen.getByLabelText("Message Lucid"), "Hello Lucid{Enter}");

    expect(await screen.findByRole("heading", { name: "Hello!" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Message Lucid")).not.toBeDisabled();
    });
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
    expect(modelPicker()).not.toBeDisabled();
  });

  it("disables the composer while a response is streaming", async () => {
    const gate = { close: () => {} };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/models") {
          return modelsResponse();
        }
        if (url === "/api/chat") {
          const encoder = new TextEncoder();
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(encoder.encode(metaFrame()));
              controller.enqueue(encoder.encode('event: delta\ndata: {"text":"thinking"}\n\n'));
              gate.close = () => controller.close();
            },
          });
          return new Response(body, {
            status: 200,
            headers: { "Content-Type": "text/event-stream" },
          });
        }
        if (url.startsWith("/api/conversations?")) {
          return jsonResponse({ items: [], next_cursor: null, has_more: false });
        }
        if (url === `/api/conversations/${CONVERSATION_ID}`) {
          return jsonResponse({ ...conversationDetail, messages: [] });
        }
        throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${url}`);
      }),
    );
    const user = userEvent.setup();

    renderApp();

    await user.type(screen.getByLabelText("Message Lucid"), "Hello Lucid{Enter}");

    expect(await screen.findByRole("button", { name: "Stop" })).toBeInTheDocument();
    expect(screen.getByLabelText("Message Lucid")).toBeDisabled();
    expect(modelPicker()).toBeDisabled();

    gate.close();
    await waitFor(() => {
      expect(screen.getByLabelText("Message Lucid")).not.toBeDisabled();
    });
  });

  it("deletes a conversation only after confirmation", async () => {
    installFetchMock();
    const user = userEvent.setup();

    renderApp();

    const deleteButton = await screen.findByRole("button", {
      name: "Delete conversation Hello Lucid",
    });
    await user.click(deleteButton);

    expect(screen.getByRole("dialog", { name: "Delete conversation?" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();

    await user.click(deleteButton);
    await user.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("opens the dashboard without unmounting the chat", async () => {
    installFetchMock();
    const user = userEvent.setup();

    renderApp();
    await screen.findByRole("button", { name: "Hello Lucid" });

    await user.click(screen.getByRole("button", { name: "Dashboard" }));

    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText("92.8%")).toBeInTheDocument();
    // Hidden, not unmounted: switching views must not abort an in-flight chat stream.
    expect(screen.getByLabelText("Message Lucid")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Hello Lucid" }));

    expect(screen.queryByRole("heading", { name: "Dashboard" })).toBeNull();
    expect(await screen.findByRole("heading", { name: "Hello Lucid" })).toBeInTheDocument();
  });

  it("opens and closes the mobile navigation drawer", async () => {
    installFetchMock();
    const user = userEvent.setup();

    renderApp();
    await screen.findByRole("button", { name: "Hello Lucid" });

    expect(screen.queryByRole("button", { name: "Close navigation" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByRole("button", { name: "Close navigation" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("button", { name: "Close navigation" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    await user.click(screen.getByRole("button", { name: "Close navigation" }));
    expect(screen.queryByRole("button", { name: "Close navigation" })).toBeNull();
  });
});
