import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { deleteConversation, getConversation, listConversations } from "../api/client";
import type { Message } from "../api/types";
import type { ChatError } from "../lib/chat-types";
import { groupConversations, type ConversationGroup } from "../lib/grouping";
import { useChatStream } from "./chat/useChatStream";

export type { ChatError } from "../lib/chat-types";

export interface ChatController {
  groups: ConversationGroup[];
  hasConversations: boolean;
  currentId: string | null;
  messages: Message[];
  streamingText: string;
  error: ChatError | null;
  streaming: boolean;
  stopping: boolean;
  hasMore: boolean;
  loadingMore: boolean;
  loadMore: () => void;
  send: (content: string) => Promise<void>;
  retry: (messageId: string) => Promise<void>;
  stop: () => Promise<void>;
  openConversation: (id: string) => Promise<void>;
  newChat: () => void;
  removeConversation: (id: string) => Promise<void>;
}

export function useChat(): ChatController {
  const queryClient = useQueryClient();
  const [currentId, setCurrentId] = useState<string | null>(null);
  const currentIdRef = useRef(currentId);
  const stream = useChatStream({ onConversation: setCurrentId });
  const resetStream = stream.reset;

  useEffect(() => {
    currentIdRef.current = currentId;
  }, [currentId]);

  const conversationsQuery = useInfiniteQuery({
    queryKey: ["conversations"],
    queryFn: ({ pageParam, signal }) => listConversations(pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.next_cursor : undefined),
    retry: false,
  });

  // Reads pause while streaming so the optimistic turn is not duplicated.
  const conversationQuery = useQuery({
    queryKey: ["conversation", currentId],
    queryFn: ({ signal }) => getConversation(currentId as string, signal),
    enabled: currentId !== null && !stream.streaming,
    retry: false,
  });

  const conversations = useMemo(
    () => conversationsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [conversationsQuery.data],
  );
  const groups = useMemo(() => groupConversations(conversations), [conversations]);

  const messages = useMemo(() => {
    const persisted = conversationQuery.data?.messages ?? [];
    if (stream.pendingUser === null) {
      return persisted;
    }
    const optimistic: Message = {
      id: "optimistic",
      role: "user",
      seq: Number.MAX_SAFE_INTEGER,
      content: stream.pendingUser,
      created_at: new Date().toISOString(),
      attempt: null,
    };
    return [...persisted, optimistic];
  }, [conversationQuery.data, stream.pendingUser]);

  const newChat = useCallback(() => {
    setCurrentId(null);
    resetStream(null);
  }, [resetStream]);

  const openConversation = useCallback(
    async (id: string) => {
      setCurrentId(id);
      resetStream(id);
    },
    [resetStream],
  );
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: async (_result, id) => {
      if (currentIdRef.current === id) {
        newChat();
      }
      await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.removeQueries({ queryKey: ["conversation", id] });
    },
  });

  const removeConversation = useCallback(
    async (id: string) => {
      await deleteMutation.mutateAsync(id);
    },
    [deleteMutation],
  );

  const loadMore = useCallback(() => {
    if (conversationsQuery.hasNextPage && !conversationsQuery.isFetchingNextPage) {
      void conversationsQuery.fetchNextPage();
    }
  }, [conversationsQuery]);

  return {
    groups,
    hasConversations: conversations.length > 0,
    currentId,
    messages,
    streamingText: stream.streamingText,
    error: stream.error,
    streaming: stream.streaming,
    stopping: stream.stopping,
    hasMore: conversationsQuery.hasNextPage,
    loadingMore: conversationsQuery.isFetchingNextPage,
    loadMore,
    send: stream.send,
    retry: stream.retry,
    stop: stream.stop,
    openConversation,
    newChat,
    removeConversation,
  };
}
