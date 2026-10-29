import { useEffect, useRef } from "react";

import type { Message } from "../api/types";
import type { ChatError } from "../lib/chat-types";
import { AssistantTurn } from "./chat/AssistantTurn";
import { ErrorNotice } from "./chat/ErrorNotice";
import { StreamingTurn } from "./chat/StreamingTurn";
import { UserTurn } from "./chat/UserTurn";

interface MessageListProps {
  messages: Message[];
  streamingText: string;
  streaming: boolean;
  error: ChatError | null;
  onRetry: (messageId: string) => void;
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
        {messages.map((message, index) =>
          message.role === "user" ? (
            <UserTurn
              key={message.id}
              message={message}
              hasAssistantReply={messages[index + 1]?.role === "assistant"}
              streaming={streaming}
              onRetry={onRetry}
            />
          ) : (
            <AssistantTurn key={message.id} message={message} />
          ),
        )}

        {streaming ? <StreamingTurn text={streamingText} /> : null}

        {error ? (
          <ErrorNotice
            error={error}
            lastUserMessage={lastUserMessage ?? null}
            streaming={streaming}
            onRetry={onRetry}
          />
        ) : null}
      </div>
    </main>
  );
}
