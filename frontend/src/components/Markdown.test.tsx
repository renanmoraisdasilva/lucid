import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Markdown } from "./Markdown";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Markdown", () => {
  it("renders headings, lists, tables and code", () => {
    render(
      <Markdown
        content={
          "# Title\n\n- one\n- two\n\n| a | b |\n| - | - |\n| 1 | 2 |\n\n```ts\nconst x = 1;\n```"
        }
      />,
    );

    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("ts")).toBeInTheDocument();
  });

  it("strips scripts, iframes and raw HTML", () => {
    const { container } = render(
      <Markdown
        content={
          '# Safe\n\n<script>alert(\'xss\')</script>\n\n<iframe src="https://evil.test"></iframe>\n\n<img src=x onerror="alert(1)" />'
        }
      />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("neutralises javascript: links", () => {
    render(<Markdown content={"[click me](javascript:alert(1))"} />);

    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("click me")).toBeInTheDocument();
  });

  it("opens safe links in a new tab", () => {
    render(<Markdown content={"[docs](https://example.com/docs)"} />);

    const link = screen.getByRole("link", { name: "docs" });

    expect(link).toHaveAttribute("href", "https://example.com/docs");
    expect(link).toHaveAttribute("rel", "noreferrer noopener");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("copies code without the line-number gutter", async () => {
    const user = userEvent.setup();
    // userEvent installs a clipboard stub in jsdom; spy on it rather than
    // replacing navigator.clipboard ourselves.
    const writeText = vi.spyOn(navigator.clipboard, "writeText");

    render(<Markdown content={"```go\npackage main\n```"} />);
    await user.click(screen.getByRole("button", { name: /copy go code/i }));

    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText.mock.calls[0][0]).toContain("package main");
    expect(screen.getByText("Copied")).toBeInTheDocument();
  });

  it("defaults the language label when none is given", () => {
    render(<Markdown content={"```\nplain\n```"} />);

    expect(screen.getByText("text")).toBeInTheDocument();
  });
});
