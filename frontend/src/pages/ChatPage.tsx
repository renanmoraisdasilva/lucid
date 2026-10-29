import { MessageList } from "../components/MessageList";
import { Composer } from "../components/Composer";
import type { ChatController } from "../hooks/useChat";

export function ChatPage({ chat }: { chat: ChatController }) {
  const title =
    chat.currentId === null
      ? "New chat"
      : (chat.groups.flatMap((group) => group.items).find((item) => item.id === chat.currentId)
          ?.title ?? "Conversation");

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center border-b border-surface-border px-4 sm:px-6">
        <h1 className="truncate text-[14px] font-medium">{title}</h1>
      </header>

      <MessageList
        messages={chat.messages}
        streamingText={chat.streamingText}
        streaming={chat.streaming}
        error={chat.error}
        onRetry={(messageId) => void chat.retry(messageId)}
      />

      <Composer
        streaming={chat.streaming}
        stopping={chat.stopping}
        onSend={(content) => void chat.send(content)}
        onStop={() => void chat.stop()}
      />
    </div>
  );
}
