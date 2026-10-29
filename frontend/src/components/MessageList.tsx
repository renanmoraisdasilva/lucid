import { useEffect, useRef } from "react";

import type { Message } from "../api/types";
import type { ChatError } from "../hooks/useChat";
import { Markdown } from "./Markdown";

interface MessageListProps {
  messages: Message[];
  streamingText: string;
  streaming: boolean;
  error: ChatError | null;
  onRetry: (messageId: string) => void;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function UsageLine({ message }: { message: Message }) {
  const usage = message.attempt?.usage ?? null;
  if (usage === null || (usage.input_tokens === null && usage.output_tokens === null)) {
    return <span className="font-mono text-[11px] text-text-muted">usage unavailable</span>;
  }
  return (
    <span className="font-mono text-[11px] text-text-muted">
      {usage.input_tokens ?? "?"} in &middot; {usage.output_tokens ?? "?"} out
    </span>
  );
}

export function MessageList({
  messages,
  streamingText,
  streaming,
  error,
  onRetry,
}: MessageListProps) {
  const scrollRef = useRef<HTMLElement | null>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    const element = scrollRef.current;
    if (element && stickToBottom.current) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, streamingText]);

  const lastUserMessage = [...messages].reverse().find((message) => message.role === "user");

  if (messages.length === 0 && !streaming) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-full border border-surface-border-subtle bg-surface-elevated">
          <span className="h-7 w-7 rounded-full border-2 border-amber-accent" />
        </span>
        <h2 className="mt-6 text-[26px] font-semibold tracking-tight">How can Lucid help today?</h2>
        <p className="mt-2 max-w-md text-[14px] leading-relaxed text-text-secondary">
          Ask a question, paste something to review, or start with a short prompt.
        </p>
      </main>
    );
  }

  return (
    <main
      ref={scrollRef}
      onScroll={(event) => {
        const element = event.currentTarget;
        stickToBottom.current =
          element.scrollHeight - element.scrollTop - element.clientHeight < 80;
      }}
      className="flex-1 overflow-y-auto px-4 py-6 sm:px-8"
    >
      <div className="mx-auto w-full max-w-3xl space-y-7">
        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex flex-col items-end">
              <span className="mb-1.5 text-[11px] text-text-muted">
                {formatTime(message.created_at)}
              </span>
              <div className="max-w-[94%] whitespace-pre-wrap rounded-2xl rounded-tr-xs border border-surface-border-subtle bg-surface-elevated p-4 text-[14px] leading-relaxed shadow-sm sm:max-w-[85%]">
                {message.content}
              </div>
              {message.attempt?.retryable ? (
                <button
                  type="button"
                  onClick={() => onRetry(message.id)}
                  disabled={streaming}
                  className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-surface-border-subtle px-2.5 py-1.5 text-[12px] font-medium text-text-secondary transition-colors hover:bg-surface-elevated hover:text-text-primary disabled:opacity-50"
                >
                  Retry
                </button>
              ) : null}
            </div>
          ) : (
            <article key={message.id} className="flex flex-col gap-3">
              <header className="flex flex-wrap items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full border border-amber-border bg-surface-elevated">
                  <span className="h-3.5 w-3.5 rounded-full border border-amber-accent" />
                </span>
                <span className="text-[15px] font-medium">Lucid</span>
                <UsageLine message={message} />
                {message.attempt?.status === "interrupted" ? (
                  <span className="rounded-full border border-amber-border bg-amber-dim px-2 py-0.5 text-[11px] font-medium text-amber-accent">
                    Interrupted
                  </span>
                ) : null}
                {message.attempt?.status === "failed" ? (
                  <span className="rounded-full border border-danger-border bg-danger-dim px-2 py-0.5 text-[11px] font-medium text-danger">
                    Failed
                  </span>
                ) : null}
              </header>
              <Markdown content={message.content} />
            </article>
          ),
        )}

        {streaming ? (
          <article className="flex flex-col gap-3" aria-live="polite">
            <header className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full border border-amber-border bg-surface-elevated">
                <span className="h-3.5 w-3.5 animate-pulse rounded-full border border-amber-accent" />
              </span>
              <span className="text-[15px] font-medium">Lucid</span>
              <span className="font-mono text-[11px] text-text-muted">streaming</span>
            </header>
            <div className="markdown whitespace-pre-wrap text-[15px] leading-relaxed">
              {streamingText}
              <span className="ml-0.5 inline-block h-[1.1em] w-[2px] animate-pulse bg-amber-accent align-[-0.15em]" />
            </div>
          </article>
        ) : null}

        {error ? (
          <div
            role="alert"
            className="rounded-xl border border-danger-border bg-danger-dim p-4 text-[13px]"
          >
            <p className="font-medium text-text-primary">{error.message}</p>
            <p className="mt-1 text-text-secondary">
              Your message is saved.
              {error.retryable && lastUserMessage
                ? " Retrying reuses it and starts a new attempt."
                : ""}
            </p>
            {error.retryable && lastUserMessage ? (
              <button
                type="button"
                onClick={() => onRetry(lastUserMessage.id)}
                disabled={streaming}
                className="mt-3 rounded-lg border border-surface-border-subtle bg-surface-elevated px-3 py-1.5 text-[12px] font-medium transition-colors hover:bg-surface-hover disabled:opacity-50"
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </main>
  );
}
