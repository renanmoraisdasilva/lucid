import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, stopGeneration, streamChat, streamRetry } from "../../api/client";
import type { StreamEvent } from "../../api/types";
import { useChatStream } from "./useChatStream";

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    streamChat: vi.fn(),
    streamRetry: vi.fn(),
    stopGeneration: vi.fn(),
  };
});

const mockedStreamChat = vi.mocked(streamChat);
const mockedStreamRetry = vi.mocked(streamRetry);
const mockedStop = vi.mocked(stopGeneration);

const meta: StreamEvent = {
  type: "meta",
  data: {
    conversation_id: "c1",
    conversation_title: "T",
    user_message_id: "u1",
    attempt_id: "a1",
    model: "fake-model",
    is_new_conversation: true,
  },
};

const done: StreamEvent = {
  type: "done",
  data: {
    attempt_id: "a1",
    status: "completed",
    assistant_message_id: "m1",
    finish_reason: "stop",
  },
};

async function* streamFrom(events: StreamEvent[]): AsyncGenerator<StreamEvent> {
  for (const event of events) {
    yield event;
  }
}

let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.clearAllMocks();
});

describe("useChatStream", () => {
  it("consumes a stream and reports the conversation", async () => {
    mockedStreamChat.mockResolvedValue(
      streamFrom([meta, { type: "delta", data: { text: "Hello" } }, done]),
    );
    const onConversation = vi.fn();
    const { result } = renderHook(() => useChatStream({ onConversation }), { wrapper });

    await act(async () => {
      await result.current.send("hi", "openai:openai/gpt-oss-120b");
    });

    expect(mockedStreamChat).toHaveBeenCalledWith(
      expect.objectContaining({
        content: "hi",
        modelId: "openai:openai/gpt-oss-120b",
      }),
    );
    expect(onConversation).toHaveBeenCalledWith("c1");
    expect(result.current.error).toBeNull();
    expect(result.current.streaming).toBe(false);
    expect(result.current.streamingText).toBe("");
  });

  it("turns an SSE error event into a chat error", async () => {
    mockedStreamChat.mockResolvedValue(
      streamFrom([
        meta,
        {
          type: "error",
          data: {
            code: "provider_rate_limited",
            message: "Slow down.",
            retryable: true,
            attempt_id: "a1",
            retry_after_seconds: 4,
          },
        },
      ]),
    );
    const { result } = renderHook(() => useChatStream({ onConversation: vi.fn() }), { wrapper });

    await act(async () => {
      await result.current.send("hi", null);
    });

    expect(result.current.error).toMatchObject({
      code: "provider_rate_limited",
      retryable: true,
      retryAfterSeconds: 4,
    });
  });

  it("turns a request rejection into a chat error", async () => {
    mockedStreamChat.mockRejectedValue(new ApiError("generation_in_progress", "Busy.", 409));
    const { result } = renderHook(() => useChatStream({ onConversation: vi.fn() }), { wrapper });

    await act(async () => {
      await result.current.send("hi", null);
    });

    expect(result.current.error).toMatchObject({
      code: "generation_in_progress",
      retryable: false,
    });
  });

  it("ignores blank messages", async () => {
    const { result } = renderHook(() => useChatStream({ onConversation: vi.fn() }), { wrapper });

    await act(async () => {
      await result.current.send("   ", null);
    });

    expect(mockedStreamChat).not.toHaveBeenCalled();
  });

  it("clears the previous error on reset", async () => {
    mockedStreamChat.mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useChatStream({ onConversation: vi.fn() }), { wrapper });

    await act(async () => {
      await result.current.send("hi", null);
    });
    expect(result.current.error).not.toBeNull();

    act(() => {
      result.current.reset("c1");
    });

    expect(result.current.error).toBeNull();
  });

  it("retries using the conversation from reset", async () => {
    mockedStreamRetry.mockResolvedValue(streamFrom([meta, done]));
    const { result } = renderHook(() => useChatStream({ onConversation: vi.fn() }), { wrapper });

    act(() => {
      result.current.reset("c1");
    });
    await act(async () => {
      await result.current.retry("m1", "gemini:gemini-3.6-flash");
    });

    expect(mockedStreamRetry).toHaveBeenCalledWith(
      expect.objectContaining({
        conversationId: "c1",
        messageId: "m1",
        modelId: "gemini:gemini-3.6-flash",
      }),
    );
    expect(mockedStop).not.toHaveBeenCalled();
  });
});
