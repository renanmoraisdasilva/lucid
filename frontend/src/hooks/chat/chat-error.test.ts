import { describe, expect, it } from "vitest";

import { ApiError } from "../../api/client";
import { isAbortError, toChatError } from "./chat-error";

describe("toChatError", () => {
  it("uses the API error code and keeps the message id", () => {
    const error = toChatError(new ApiError("retry_failed", "Nope.", 409), "fallback", true, "m1");

    expect(error).toEqual({
      code: "retry_failed",
      message: "Nope.",
      retryable: true,
      messageId: "m1",
      retryAfterSeconds: null,
    });
  });

  it("falls back for a non-Error rejection", () => {
    const error = toChatError("boom", "request_failed", false);

    expect(error.code).toBe("request_failed");
    expect(error.message).toBe("The response stream failed.");
    expect(error.messageId).toBeNull();
  });
});

describe("isAbortError", () => {
  it("recognizes an AbortError", () => {
    expect(isAbortError(new DOMException("aborted", "AbortError"))).toBe(true);
  });

  it("rejects other errors", () => {
    expect(isAbortError(new Error("boom"))).toBe(false);
    expect(isAbortError("boom")).toBe(false);
  });
});
