import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const MODEL_ID = "openai:openai/gpt-oss-120b";

const catalogue = {
  items: [
    {
      id: MODEL_ID,
      label: "openai/gpt-oss-120b \u00b7 Groq",
      provider: "openai_compatible",
      model: "openai/gpt-oss-120b",
    },
  ],
  default_id: MODEL_ID,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe("model catalogue loading", () => {
  it("retries when the API is not ready yet instead of hiding the picker", async () => {
    let attempts = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input.toString();
        if (url === "/api/models") {
          attempts += 1;
          if (attempts === 1) {
            return jsonResponse({ error: { code: "unavailable", message: "Not ready." } }, 503);
          }
          return jsonResponse(catalogue);
        }
        if (url.startsWith("/api/conversations?")) {
          return jsonResponse({ items: [], next_cursor: null, has_more: false });
        }
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    renderApp();

    expect(
      await screen.findByRole("button", { name: /^Model: / }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(attempts).toBeGreaterThanOrEqual(2);
  });
});
