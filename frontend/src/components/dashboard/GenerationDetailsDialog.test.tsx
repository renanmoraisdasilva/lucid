import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DashboardRecentAttempt } from "../../api/types";
import { GenerationDetailsDialog } from "./GenerationDetailsDialog";

const completed: DashboardRecentAttempt = {
  attempt_id: "a1",
  started_at: "2026-10-29T10:41:00Z",
  conversation_id: "c1",
  conversation_title: "Event-Driven Architecture & Bus",
  status: "completed",
  model: "gemini-3.6-flash",
  attempt_no: 1,
  retry_count: 0,
  input_tokens: 8412,
  output_tokens: 1284,
  ttft_ms: 486,
  duration_ms: 2600,
  http_status: 200,
  context_tokens: 8812,
  error_code: null,
  error_message: null,
};

describe("GenerationDetailsDialog", () => {
  it("shows completed metadata without an error block", () => {
    render(<GenerationDetailsDialog attempt={completed} onClose={() => {}} />);

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("8,412")).toBeInTheDocument();
    expect(within(dialog).getByText("1,284")).toBeInTheDocument();
    expect(within(dialog).getByText("8,812")).toBeInTheDocument();
    expect(within(dialog).getByText("486 ms")).toBeInTheDocument();
    expect(within(dialog).getByText("2.6 s")).toBeInTheDocument();
    expect(within(dialog).getByText("200")).toBeInTheDocument();
    expect(within(dialog).getByText("None")).toBeInTheDocument();
    expect(within(dialog).queryByText("Error")).toBeNull();
  });

  it("closes on Escape and restores the previous focus", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();

    const { unmount } = render(<GenerationDetailsDialog attempt={completed} onClose={onClose} />);
    expect(screen.getByRole("button", { name: "Close generation details" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);

    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("closes when the backdrop is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<GenerationDetailsDialog attempt={completed} onClose={onClose} />);
    await user.click(screen.getByRole("heading", { name: "Event-Driven Architecture & Bus" }));
    expect(onClose).not.toHaveBeenCalled();

    await user.click(screen.getByRole("dialog").parentElement as HTMLElement);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
