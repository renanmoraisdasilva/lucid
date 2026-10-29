import { useEffect, useState } from "react";

import type { Message } from "../../api/types";
import type { ChatError } from "../../lib/chat-types";
import { formatWait } from "../../lib/duration";

/** Retry action that respects the provider's cool-down. */
function RetryAction({
  retryAfterSeconds,
  disabled,
  onRetry,
}: {
  retryAfterSeconds: number | null;
  disabled: boolean;
  onRetry: () => void;
}) {
  const [remaining, setRemaining] = useState(() => Math.ceil(retryAfterSeconds ?? 0));

  useEffect(() => {
    if (remaining <= 0) {
      return;
    }
    const id = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(id);
  }, [remaining]);

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={onRetry}
        disabled={disabled || remaining > 0}
        className="rounded-lg border border-surface-border-subtle bg-surface-elevated px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {remaining > 0 ? `Retry in ${formatWait(remaining)}` : "Retry"}
      </button>
      {remaining > 0 ? (
        <span className="text-[12px] text-text-muted">
          The model is rate limited; waiting before trying again.
        </span>
      ) : null}
    </div>
  );
}

interface ErrorNoticeProps {
  error: ChatError;
  lastUserMessage: Message | null;
  streaming: boolean;
  onRetry: (messageId: string) => void;
}

export function ErrorNotice({ error, lastUserMessage, streaming, onRetry }: ErrorNoticeProps) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-danger-border bg-danger-dim p-4 text-[13px]"
    >
      <p className="font-medium text-text-primary">{error.message}</p>
      <p className="mt-1 text-text-secondary">
        Your message is saved.
        {error.retryable && lastUserMessage ? " Retrying reuses it and starts a new attempt." : ""}
      </p>
      {error.retryable && lastUserMessage ? (
        <RetryAction
          key={`${error.code}-${error.retryAfterSeconds ?? 0}`}
          retryAfterSeconds={error.retryAfterSeconds}
          disabled={streaming}
          onRetry={() => onRetry(lastUserMessage.id)}
        />
      ) : null}
    </div>
  );
}
