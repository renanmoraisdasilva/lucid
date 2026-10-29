import type { AttemptSummary } from "../../api/types";

/** Explain why a turn has no answer, without leaking provider internals. */
export function describeFailure(attempt: AttemptSummary): string {
  switch (attempt.error_code) {
    case "interrupted":
      return "The response was interrupted before any text arrived.";
    case "stopped_by_user":
      return "You stopped this response.";
    case "process_restart":
    case "server_shutdown":
      return "The server restarted before the answer finished.";
    case "empty_response":
      return "The model returned no text.";
    case "provider_timeout":
      return "The model did not respond in time.";
    case "provider_rate_limited":
      return "The model was rate limited.";
    case "provider_unavailable":
      return "The model was temporarily unavailable.";
    case "provider_invalid_request":
      return "The model rejected this request.";
    case "provider_safety_blocked":
      return "The model declined to answer.";
    default:
      return attempt.error_message ?? "The response failed.";
  }
}
