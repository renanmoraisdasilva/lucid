import { ApiError } from "../../api/client";
import type { ChatError } from "../../lib/chat-types";

/** Normalize a thrown value into the shape the UI already renders. */
export function toChatError(
  caught: unknown,
  fallbackCode: string,
  retryable: boolean,
  messageId: string | null = null,
): ChatError {
  return {
    code: caught instanceof ApiError ? caught.code : fallbackCode,
    message: caught instanceof Error ? caught.message : "The response stream failed.",
    retryable,
    messageId,
    retryAfterSeconds: null,
  };
}

export function isAbortError(caught: unknown): boolean {
  return caught instanceof DOMException && caught.name === "AbortError";
}
