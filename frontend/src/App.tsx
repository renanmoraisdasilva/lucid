import { useEffect, useState } from "react";

import type { ConversationSummary } from "./api/types";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Sidebar } from "./components/Sidebar";
import { useChat } from "./hooks/useChat";
import { ChatPage } from "./pages/ChatPage";
import { DashboardPage } from "./pages/DashboardPage";

type View = "chat" | "dashboard";

function AppShell() {
  const chat = useChat();
  const [view, setView] = useState<View>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ConversationSummary | null>(null);

  useEffect(() => {
    if (!sidebarOpen) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setSidebarOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [sidebarOpen]);

  useEffect(() => {
    const newChat = chat.newChat;
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setView("chat");
        newChat();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [chat.newChat]);

  const openConversation = (id: string) => {
    setSidebarOpen(false);
    setView("chat");
    void chat.openConversation(id);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-surface-bg text-text-primary">
      <Sidebar
        groups={chat.groups}
        hasConversations={chat.hasConversations}
        currentId={view === "chat" ? chat.currentId : null}
        hasMore={chat.hasMore}
        loadingMore={chat.loadingMore}
        activeView={view}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSelect={openConversation}
        onNew={() => {
          setSidebarOpen(false);
          setView("chat");
          chat.newChat();
        }}
        onDashboard={() => {
          setSidebarOpen(false);
          setView("dashboard");
        }}
        onDelete={(id) =>
          setDeleteTarget(
            chat.groups.flatMap((group) => group.items).find((item) => item.id === id) ?? null,
          )
        }
        onLoadMore={chat.loadMore}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className={view === "chat" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
          <ChatPage chat={chat} onOpenSidebar={() => setSidebarOpen(true)} />
        </div>
        {view === "dashboard" ? <DashboardPage onOpenSidebar={() => setSidebarOpen(true)} /> : null}
      </div>

      {sidebarOpen ? (
        <div
          aria-hidden="true"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
        />
      ) : null}

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
      <AppShell />
    </ErrorBoundary>
  );
}
