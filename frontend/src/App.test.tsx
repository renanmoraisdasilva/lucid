import { render, screen } from "@testing-library/react";

import App from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("renders the project heading", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => undefined)),
    );

    render(<App />);

    expect(screen.getByRole("heading", { name: "Lucid" })).toBeInTheDocument();
  });

  it("shows the backend as ok when the health endpoint answers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
    );

    render(<App />);

    expect(await screen.findByText("API: ok")).toBeInTheDocument();
  });

  it("reports an unreachable backend without throwing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );

    render(<App />);

    expect(await screen.findByText("API: unreachable")).toBeInTheDocument();
  });
});
