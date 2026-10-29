import { useEffect, useState } from "react";

import type { ConversationSummary } from "./api/types";
import { Composer } from "./components/Composer";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { MessageList } from "./components/MessageList";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";

function ChatWorkspace() {
  const chat = useChat();
  const [deleteTarget, setDeleteTarget] = useState<ConversationSummary | null>(null);

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
      : (chat.groups.flatMap((group) => group.items).find((item) => item.id === chat.currentId)
          ?.title ?? "Conversation");

  return (
    <div className="flex h-screen overflow-hidden bg-surface-bg text-text-primary">
      <Sidebar
        groups={chat.groups}
        hasConversations={chat.hasConversations}
        currentId={chat.currentId}
        hasMore={chat.hasMore}
        loadingMore={chat.loadingMore}
        onSelect={(id) => void chat.openConversation(id)}
        onNew={chat.newChat}
        onDelete={(id) =>
          setDeleteTarget(
            chat.groups.flatMap((group) => group.items).find((item) => item.id === id) ?? null,
          )
        }
        onLoadMore={chat.loadMore}
      />

      <div className="flex min-w-0 flex-1 flex-col">
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
          models={chat.models}
          modelId={chat.modelId}
          onSelectModel={chat.selectModel}
          onSend={(content) => void chat.send(content)}
          onStop={() => void chat.stop()}
        />
      </div>

      {deleteTarget ? (
        <ConfirmDialog
          title="Delete conversation?"
          body={`\u201c${deleteTarget.title}\u201d and its messages will be permanently deleted. This cannot be undone.`}
          confirmLabel="Delete"
          onCancel={() => setDeleteTarget(null)}
          onConfirm={() => {
            const id = deleteTarget.id;
            setDeleteTarget(null);
            void chat.removeConversation(id);
          }}
        />
      ) : null}
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ChatWorkspace />
    </ErrorBoundary>
  );
}
