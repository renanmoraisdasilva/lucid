import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Message } from "../api/types";
import { MessageList } from "./MessageList";

const USER_MESSAGE: Message = {
  id: "u1",
  role: "user",
  seq: 1,
  content: "Hello",
  created_at: "2026-10-29T10:42:00Z",
  attempt: {
    id: "a1",
    status: "failed",
    model: "fake-model",
    attempt_no: 1,
    retryable: true,
    error_code: "provider_unavailable",
    error_message: null,
    usage: null,
  },
};

const ASSISTANT_MESSAGE: Message = {
  id: "m1",
  role: "assistant",
  seq: 2,
  content: "Partial answer",
  created_at: "2026-10-29T10:42:01Z",
  attempt: {
    id: "a1",
    status: "interrupted",
    model: "fake-model",
    attempt_no: 1,
    retryable: false,
    error_code: "interrupted",
    error_message: null,
    usage: null,
  },
};

function renderList(overrides: Partial<Parameters<typeof MessageList>[0]> = {}) {
  const props = {
    messages: [USER_MESSAGE, ASSISTANT_MESSAGE],
    streamingText: "",
    streaming: false,
    error: null,
    onRetry: vi.fn(),
    ...overrides,
  };
  return { ...render(<MessageList {...props} />), onRetry: props.onRetry };
}

describe("MessageList", () => {
  it("shows an unavailable usage state instead of inventing numbers", () => {
    renderList();

    expect(screen.getByText("usage unavailable")).toBeInTheDocument();
  });

  it("marks an interrupted response", () => {
    renderList();

    expect(screen.getByText("Interrupted")).toBeInTheDocument();
    expect(screen.getByText("Partial answer")).toBeInTheDocument();
  });

  it("offers retry on a failed user message", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderList({ messages: [USER_MESSAGE] });

    expect(screen.getByText("The model was temporarily unavailable.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(onRetry).toHaveBeenCalledWith("u1");
  });

  it("keeps retry but hides the reason when a partial answer is visible", () => {
    renderList({
      messages: [
        {
          ...USER_MESSAGE,
          attempt: {
            ...USER_MESSAGE.attempt!,
            status: "interrupted",
            error_code: "interrupted",
          },
        },
        ASSISTANT_MESSAGE,
      ],
    });

    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText("The response was interrupted before any text arrived.")).toBeNull();
    expect(screen.getByText("Interrupted")).toBeInTheDocument();
  });

  it("explains an interrupted attempt that produced no text", () => {
    renderList({
      messages: [
        {
          ...USER_MESSAGE,
          attempt: {
            ...USER_MESSAGE.attempt!,
            status: "interrupted",
            error_code: "interrupted",
          },
        },
      ],
      error: null,
    });

    expect(
      screen.getByText("The response was interrupted before any text arrived."),
    ).toBeInTheDocument();
  });

  it("explains a restart during generation", () => {
    renderList({
      messages: [
        {
          ...USER_MESSAGE,
          attempt: {
            ...USER_MESSAGE.attempt!,
            status: "interrupted",
            error_code: "process_restart",
          },
        },
      ],
      error: null,
    });

    expect(
      screen.getByText("The server restarted before the answer finished."),
    ).toBeInTheDocument();
  });

  it("renders an error banner with retry for the last user message", async () => {
    const user = userEvent.setup();
    const { onRetry } = renderList({
      error: {
        code: "provider_rate_limited",
        message: "The model is rate limited right now.",
        retryable: true,
        messageId: null,
        retryAfterSeconds: null,
      },
    });

    expect(screen.getByRole("alert")).toHaveTextContent("The model is rate limited right now.");
    const buttons = screen.getAllByRole("button", { name: "Retry" });
    await user.click(buttons[buttons.length - 1]);

    expect(onRetry).toHaveBeenCalledWith("u1");
  });

  it("counts down and disables retry during the provider cool-down", () => {
    renderList({
      error: {
        code: "provider_rate_limited",
        message: "The model is rate limited right now.",
        retryable: true,
        messageId: null,
        retryAfterSeconds: 30,
      },
    });

    const button = screen.getByRole("button", { name: "Retry in 30s" });
    expect(button).toBeDisabled();
    expect(screen.getByText(/rate limited; waiting before trying again/)).toBeInTheDocument();
  });

  it("formats a daily quota wait in hours, not seconds", () => {
    renderList({
      error: {
        code: "provider_rate_limited",
        message: "The free-tier daily limit is reached.",
        retryable: true,
        messageId: null,
        retryAfterSeconds: 39760,
      },
    });

    expect(screen.getByRole("button", { name: "Retry in 11h 2m" })).toBeDisabled();
  });

  it("shows the empty state when there is nothing to show", () => {
    renderList({ messages: [] });

    expect(screen.getByRole("heading", { name: "How can Lucid help today?" })).toBeInTheDocument();
  });

  it("renders streaming text with a live region", () => {
    renderList({ streamingText: "Thinking", streaming: true });

    expect(screen.getByText("Thinking")).toBeInTheDocument();
    expect(screen.getByText("streaming")).toBeInTheDocument();
  });

  it("shows a waiting state before the first token arrives", () => {
    renderList({ streamingText: "", streaming: true });

    expect(screen.getByText("waiting")).toBeInTheDocument();
    expect(screen.getByText(/Waiting for the model/)).toBeInTheDocument();
  });
});
