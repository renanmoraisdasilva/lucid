import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { DashboardRecentAttempt } from "../../api/types";
import { RecentGenerations } from "./RecentGenerations";

function attempt(overrides: Partial<DashboardRecentAttempt> = {}): DashboardRecentAttempt {
  return {
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
    ...overrides,
  };
}

const attempts: DashboardRecentAttempt[] = [
  attempt(),
  attempt({
    attempt_id: "a2",
    conversation_title: "Retry backoff behavior",
    status: "failed",
    attempt_no: 3,
    retry_count: 2,
    input_tokens: null,
    output_tokens: null,
    ttft_ms: null,
    duration_ms: null,
    http_status: 429,
    context_tokens: 3200,
    error_code: "provider_rate_limited",
    error_message: "The model is rate limited right now.",
  }),
  attempt({
    attempt_id: "a3",
    conversation_title: "Streaming SSE edge cases",
    status: "interrupted",
    attempt_no: 2,
    retry_count: 0,
    http_status: 200,
  }),
];

describe("RecentGenerations", () => {
  it("maps the API fields onto the desktop table columns", () => {
    render(<RecentGenerations attempts={attempts} />);

    const table = screen.getByRole("table");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent);

    expect(headers).toEqual([
      "Time",
      "Conversation",
      "Status",
      "Model",
      "In",
      "Out",
      "TTFT",
      "Duration",
      "Attempt",
    ]);
    expect(within(table).getAllByRole("row")).toHaveLength(attempts.length + 1);
    expect(within(table).getByText("Completed")).toBeInTheDocument();
    expect(within(table).getByText("Failed")).toBeInTheDocument();
    expect(within(table).getByText("Interrupted")).toBeInTheDocument();
    expect(within(table).getAllByText("8,412")).toHaveLength(2);
    expect(within(table).getAllByText("486 ms")).toHaveLength(2);
    expect(within(table).getAllByText("2.6 s")).toHaveLength(2);
    expect(within(table).getByText("2 auto")).toBeInTheDocument();
    expect(within(table).getByText("1 manual")).toBeInTheDocument();
    expect(screen.getByText("Showing 3 attempts · no pagination")).toBeInTheDocument();
  });

  it("renders every attempt without pagination", () => {
    const many = Array.from({ length: 25 }, (_, index) =>
      attempt({ attempt_id: `a${index}`, attempt_no: index + 1 }),
    );

    render(<RecentGenerations attempts={many} />);

    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(26);
    expect(screen.getAllByRole("button", { name: /Open details for/ })).toHaveLength(25);
  });

  it("opens details from a row and shows the full metadata", async () => {
    const user = userEvent.setup();

    render(<RecentGenerations attempts={attempts} />);
    const failedRow = screen.getByLabelText("Open details for Retry backoff behavior", {
      selector: "tr",
    });

    await user.click(failedRow);

    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByRole("heading", { name: "Retry backoff behavior" }),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Failed")).toBeInTheDocument();
    expect(within(dialog).getByText("gemini-3.6-flash")).toBeInTheDocument();
    expect(within(dialog).getByText("#3 · 2 auto", { exact: false })).toBeInTheDocument();
    expect(within(dialog).getByText("Context tokens")).toBeInTheDocument();
    expect(within(dialog).getByText("3,200")).toBeInTheDocument();
    expect(within(dialog).getByText("429")).toBeInTheDocument();
    expect(within(dialog).getByText("2 automatic")).toBeInTheDocument();
    expect(within(dialog).getByText("provider_rate_limited")).toBeInTheDocument();
    expect(within(dialog).getByText("The model is rate limited right now.")).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "Metadata only — no prompts or message content are stored or shown here.",
      ),
    ).toBeInTheDocument();
  });

  it("opens details with the keyboard and restores focus on Escape", async () => {
    const user = userEvent.setup();

    render(<RecentGenerations attempts={attempts} />);
    const row = screen.getByLabelText("Open details for Event-Driven Architecture & Bus", {
      selector: "tr",
    });
    row.focus();

    await user.keyboard("{Enter}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close generation details" })).toHaveFocus();

    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(row).toHaveFocus();
  });

  it("closes when the backdrop is clicked", async () => {
    const user = userEvent.setup();

    render(<RecentGenerations attempts={attempts} />);
    await user.click(
      screen.getByLabelText("Open details for Event-Driven Architecture & Bus", { selector: "tr" }),
    );

    await user.click(screen.getByRole("dialog").parentElement as HTMLElement);

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens details from a mobile card", async () => {
    const user = userEvent.setup();

    render(<RecentGenerations attempts={attempts} />);
    await user.click(
      screen.getByRole("button", { name: "Open details for Retry backoff behavior" }),
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("provider_rate_limited")).toBeInTheDocument();
  });

  it("explains an empty range", () => {
    render(<RecentGenerations attempts={[]} />);

    expect(screen.getByText("No generations in this range")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
