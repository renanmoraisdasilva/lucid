import { describe, expect, it, vi } from "vitest";

import type { StreamEvent } from "../../api/types";
import { applyEvent } from "./stream-events";

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

describe("applyEvent", () => {
  it("forwards meta and delta events", () => {
    const onMeta = vi.fn();
    const onDelta = vi.fn();

    expect(applyEvent(meta, { onMeta, onDelta })).toBeNull();
    expect(applyEvent({ type: "delta", data: { text: "hi" } }, { onMeta, onDelta })).toBeNull();

    expect(onMeta).toHaveBeenCalledWith(meta.data);
    expect(onDelta).toHaveBeenCalledWith("hi");
  });

  it("returns a chat error for an error event", () => {
    const failure = applyEvent(
      {
        type: "error",
        data: {
          code: "provider_rate_limited",
          message: "Slow down.",
          retryable: true,
          attempt_id: "a1",
          retry_after_seconds: 7,
        },
      },
      { onMeta: vi.fn(), onDelta: vi.fn() },
    );

    expect(failure).toEqual({
      code: "provider_rate_limited",
      message: "Slow down.",
      retryable: true,
      messageId: null,
      retryAfterSeconds: 7,
    });
  });

  it("ignores usage and done events", () => {
    const onMeta = vi.fn();
    const onDelta = vi.fn();

    expect(
      applyEvent(
        {
          type: "usage",
          data: { input_tokens: 1, output_tokens: 2, thought_tokens: 0, total_tokens: 3 },
        },
        { onMeta, onDelta },
      ),
    ).toBeNull();
    expect(
      applyEvent(
        {
          type: "done",
          data: {
            attempt_id: "a1",
            status: "completed",
            assistant_message_id: "m1",
            finish_reason: "stop",
          },
        },
        { onMeta, onDelta },
      ),
    ).toBeNull();
    expect(onMeta).not.toHaveBeenCalled();
    expect(onDelta).not.toHaveBeenCalled();
  });
});
