import type { Message } from "../../api/types";
import { describeFailure } from "./failure-text";

interface UserTurnProps {
  message: Message;
  hasAssistantReply: boolean;
  streaming: boolean;
  onRetry: (messageId: string) => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function UserTurn({ message, hasAssistantReply, streaming, onRetry }: UserTurnProps) {
  return (
    <div className="flex flex-col items-end">
      <span className="mb-1.5 text-[11px] text-text-muted">{formatTime(message.created_at)}</span>
      <div className="max-w-[94%] whitespace-pre-wrap rounded-2xl rounded-tr-xs border border-surface-border-subtle bg-surface-elevated p-4 text-[14px] leading-relaxed shadow-sm sm:max-w-[85%]">
        {message.content}
      </div>
      {message.attempt?.retryable ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {hasAssistantReply ? null : (
            <span className="text-[12px] text-text-muted">{describeFailure(message.attempt)}</span>
          )}
          <button
            type="button"
            onClick={() => onRetry(message.id)}
            disabled={streaming}
            className="inline-flex items-center gap-1.5 rounded-lg border border-surface-border-subtle px-2.5 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:bg-surface-elevated hover:text-text-primary disabled:opacity-50"
          >
            Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}
