import { useEffect } from "react";

import { Composer } from "./components/Composer";
import { MessageList } from "./components/MessageList";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";

export default function App() {
  const chat = useChat();

  useEffect(() => {
    const newChat = chat.newChat;
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        newChat();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [chat.newChat]);

  const title =
    chat.currentId === null
      ? "New chat"
      : (chat.conversations.find((item) => item.id === chat.currentId)?.title ?? "Conversation");

  return (
    <div className="flex h-screen overflow-hidden bg-surface-bg text-text-primary">
      <Sidebar
        conversations={chat.conversations}
        currentId={chat.currentId}
        onSelect={(id) => void chat.openConversation(id)}
        onNew={chat.newChat}
        onDelete={(id) => {
          if (window.confirm("Delete this conversation permanently?")) {
            void chat.removeConversation(id);
          }
        }}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center border-b border-surface-border px-4 sm:px-6">
          <h1 className="truncate text-[14px] font-medium">{title}</h1>
        </header>

        <MessageList
          messages={chat.messages}
          streamingText={chat.streamingText}
          streaming={chat.streaming}
          usage={chat.usage}
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
    </div>
  );
}
