import type { MetaEvent, StreamEvent } from "../../api/types";
import type { ChatError } from "../../lib/chat-types";

export interface ChatStreamController {
  pendingUser: string | null;
  streamingText: string;
  error: ChatError | null;
  streaming: boolean;
  stopping: boolean;
  send: (content: string) => Promise<void>;
  retry: (messageId: string) => Promise<void>;
  stop: () => Promise<void>;
  reset: (conversationId: string | null) => void;
}

interface StreamHandlers {
  onMeta: (data: MetaEvent) => void;
  onDelta: (text: string) => void;
}

/** Fold one SSE event into the stream state, returning a failure if it carries one. */
export function applyEvent(event: StreamEvent, handlers: StreamHandlers): ChatError | null {
  switch (event.type) {
    case "meta":
      handlers.onMeta(event.data);
      return null;
    case "delta":
      handlers.onDelta(event.data.text);
      return null;
    case "error":
      return {
        code: event.data.code,
        message: event.data.message,
        retryable: event.data.retryable,
        messageId: null,
        retryAfterSeconds: event.data.retry_after_seconds ?? null,
      };
    default:
      return null;
  }
}
