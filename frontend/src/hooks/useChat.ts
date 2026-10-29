import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { deleteConversation, getConversation, getModels, listConversations } from "../api/client";
import type { Message, ModelOption } from "../api/types";
import type { ChatError } from "../lib/chat-types";
import { groupConversations, type ConversationGroup } from "../lib/grouping";
import { useChatStream } from "./chat/useChatStream";

const MODEL_STORAGE_KEY = "lucid.model";

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
  models: ModelOption[];
  modelId: string | null;
  selectModel: (id: string) => void;
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

  const modelsQuery = useQuery({
    queryKey: ["models"],
    queryFn: ({ signal }) => getModels(signal),
    staleTime: Infinity,
    retry: false,
  });

  const [modelId, setModelId] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem(MODEL_STORAGE_KEY),
  );

  const models = useMemo<ModelOption[]>(() => modelsQuery.data?.items ?? [], [modelsQuery.data]);
  const defaultModelId = modelsQuery.data?.default_id ?? null;
  const effectiveModelId =
    modelId !== null && models.some((option) => option.id === modelId) ? modelId : defaultModelId;

  const selectModel = useCallback((id: string) => {
    setModelId(id);
    window.localStorage.setItem(MODEL_STORAGE_KEY, id);
  }, []);

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

  const sendStream = stream.send;
  const retryStream = stream.retry;

  const send = useCallback(
    (content: string) => sendStream(content, effectiveModelId),
    [effectiveModelId, sendStream],
  );

  const retry = useCallback(
    (messageId: string) => retryStream(messageId, effectiveModelId),
    [effectiveModelId, retryStream],
  );

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
    models,
    modelId: effectiveModelId,
    selectModel,
    loadMore,
    send,
    retry,
    stop: stream.stop,
    openConversation,
    newChat,
    removeConversation,
  };
}
