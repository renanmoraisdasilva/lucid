import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "./Composer";

function composer(streaming: boolean) {
  return (
    <Composer
      streaming={streaming}
      stopping={false}
      models={[]}
      modelId={null}
      onSelectModel={vi.fn()}
      onSend={vi.fn()}
      onStop={vi.fn()}
    />
  );
}

describe("Composer focus", () => {
  it("puts the caret back when a response finishes", () => {
    const { rerender } = render(composer(false));
    const textarea = screen.getByLabelText("Message Lucid");

    textarea.focus();
    expect(textarea).toHaveFocus();

    // A browser blurs a focused control when it becomes disabled. jsdom keeps
    // focus on disabled elements, so blur it while it is still enabled to
    // reproduce what the browser actually leaves behind.
    textarea.blur();
    rerender(composer(true));
    expect(textarea).toBeDisabled();
    expect(textarea).not.toHaveFocus();

    rerender(composer(false));

    expect(textarea).toHaveFocus();
  });

  it("leaves focus alone when the user moved elsewhere", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <div>
        <button type="button">Elsewhere</button>
        {composer(false)}
      </div>,
    );
    const elsewhere = screen.getByRole("button", { name: "Elsewhere" });
    await user.click(elsewhere);
    expect(elsewhere).toHaveFocus();

    rerender(
      <div>
        <button type="button">Elsewhere</button>
        {composer(true)}
      </div>,
    );
    rerender(
      <div>
        <button type="button">Elsewhere</button>
        {composer(false)}
      </div>,
    );

    expect(elsewhere).toHaveFocus();
  });
});
