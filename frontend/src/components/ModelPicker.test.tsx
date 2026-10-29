import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ModelOption } from "../api/types";
import { ModelPicker } from "./ModelPicker";

const MODELS: ModelOption[] = [
  {
    id: "openai:openai/gpt-oss-120b",
    label: "openai/gpt-oss-120b \u00b7 Groq",
    provider: "openai_compatible",
    model: "openai/gpt-oss-120b",
  },
  {
    id: "openai:qwen/qwen3.8-27b",
    label: "qwen/qwen3.8-27b \u00b7 Groq",
    provider: "openai_compatible",
    model: "qwen/qwen3.8-27b",
  },
  {
    id: "gemini:gemini-3.6-flash",
    label: "gemini-3.6-flash \u00b7 Gemini",
    provider: "gemini",
    model: "gemini-3.6-flash",
  },
];

function renderPicker(options: { value?: string | null; disabled?: boolean } = {}) {
  const onChange = vi.fn();
  render(
    <ModelPicker
      models={MODELS}
      value={options.value === undefined ? MODELS[0].id : options.value}
      disabled={options.disabled}
      onChange={onChange}
    />,
  );
  return { onChange, trigger: screen.getByRole("button", { name: /^Model: / }) };
}

describe("ModelPicker", () => {
  it("shows the current model and the endpoint separately", () => {
    const { trigger } = renderPicker();

    expect(trigger).toHaveTextContent("openai/gpt-oss-120b");
    expect(trigger).toHaveTextContent("Groq");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("opens the listbox and marks the selected option", async () => {
    const user = userEvent.setup();
    const { trigger } = renderPicker();

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    expect(options[2]).toHaveAttribute("aria-selected", "false");
  });

  it("selects an option with the mouse and closes", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = renderPicker();

    await user.click(trigger);
    await user.click(screen.getByRole("option", { name: /gemini-3\.6-flash/ }));

    expect(onChange).toHaveBeenCalledWith("gemini:gemini-3.6-flash");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("moves with the arrow keys and selects with Enter", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = renderPicker();

    await user.click(trigger);
    await user.keyboard("{ArrowDown}{Enter}");

    expect(onChange).toHaveBeenCalledWith(MODELS[1].id);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("wraps nothing and stays inside the list at the edges", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = renderPicker({ value: MODELS[2].id });

    await user.click(trigger);
    await user.keyboard("{ArrowDown}{Enter}");

    expect(onChange).toHaveBeenCalledWith(MODELS[2].id);
  });

  it("closes on Escape without changing the selection", async () => {
    const user = userEvent.setup();
    const { onChange, trigger } = renderPicker();

    await user.click(trigger);
    await user.keyboard("{ArrowDown}{Escape}");

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("closes when the pointer goes elsewhere", async () => {
    const user = userEvent.setup();
    const { trigger } = renderPicker();

    await user.click(trigger);
    await user.click(document.body);

    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("does not open while disabled", async () => {
    const user = userEvent.setup();
    const { trigger } = renderPicker({ disabled: true });

    expect(trigger).toBeDisabled();
    await user.click(trigger);

    expect(screen.queryByRole("listbox")).toBeNull();
  });
});
