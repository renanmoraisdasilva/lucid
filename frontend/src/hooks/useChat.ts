import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  deleteConversation,
  getConversation,
  getModels,
  listConversations,
  stopGeneration,
  streamChat,
  streamRetry,
} from "../api/client";
import type { Message, ModelOption, StreamEvent } from "../api/types";
import { groupConversations, type ConversationGroup } from "../lib/grouping";

const MODEL_STORAGE_KEY = "lucid.model";

export interface ChatError {
  code: string;
  message: string;
  retryable: boolean;
  messageId: string | null;
  retryAfterSeconds: number | null;
}

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
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [error, setError] = useState<ChatError | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [stopping, setStopping] = useState(false);

  const conversationIdRef = useRef<string | null>(null);
  const attemptRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    // StrictMode runs mount -> cleanup -> mount in development, so the flag has
    // to be restored here; otherwise this instance believes it is unmounted for
    // the rest of the session and never clears the streaming state.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

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
    enabled: currentId !== null && !streaming,
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
    if (pendingUser === null) {
      return persisted;
    }
    const optimistic: Message = {
      id: "optimistic",
      role: "user",
      seq: Number.MAX_SAFE_INTEGER,
      content: pendingUser,
      created_at: new Date().toISOString(),
      attempt: null,
    };
    return [...persisted, optimistic];
  }, [conversationQuery.data, pendingUser]);

  const invalidate = useCallback(
    async (conversationId: string | null) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["conversations"] }),
        conversationId === null
          ? Promise.resolve()
          : queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] }),
      ]);
    },
    [queryClient],
  );

  const runStream = useCallback(
    async (events: AsyncGenerator<StreamEvent>, optimisticUserText: string | null) => {
      setStreaming(true);
      setStopping(false);
      setError(null);
      setStreamingText("");
      if (optimisticUserText !== null) {
        setPendingUser(optimisticUserText);
      }
      attemptRef.current = null;

      let text = "";
      let failed: ChatError | null = null;

      try {
        for await (const event of events) {
          if (event.type === "meta") {
            conversationIdRef.current = event.data.conversation_id;
            setCurrentId(event.data.conversation_id);
            attemptRef.current = event.data.attempt_id;
          } else if (event.type === "delta") {
            text += event.data.text;
            setStreamingText(text);
          } else if (event.type === "error") {
            failed = {
              code: event.data.code,
              message: event.data.message,
              retryable: event.data.retryable,
              messageId: null,
              retryAfterSeconds: event.data.retry_after_seconds ?? null,
            };
          }
        }
      } catch (caught) {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          failed = {
            code: caught instanceof ApiError ? caught.code : "stream_failed",
            message: caught instanceof Error ? caught.message : "The response stream failed.",
            retryable: true,
            messageId: null,
            retryAfterSeconds: null,
          };
        }
      } finally {
        if (mountedRef.current) {
          setStreaming(false);
          setStopping(false);
          setStreamingText("");
          setPendingUser(null);
          attemptRef.current = null;
        }
      }

      if (!mountedRef.current) {
        return;
      }

      await invalidate(conversationIdRef.current);
      if (failed) {
        setError(failed);
      }
    },
    [invalidate],
  );

  const send = useCallback(
    async (content: string) => {
      if (streaming || !content.trim()) {
        return;
      }
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const events = await streamChat({
          conversationId: conversationIdRef.current,
          content,
          modelId: effectiveModelId,
          signal: controller.signal,
        });
        await runStream(events, content);
      } catch (caught) {
        if (mountedRef.current) {
          setError({
            code: caught instanceof ApiError ? caught.code : "request_failed",
            message: caught instanceof Error ? caught.message : "The message could not be sent.",
            retryable: false,
            messageId: null,
            retryAfterSeconds: null,
          });
        }
      }
    },
    [effectiveModelId, runStream, streaming],
  );

  const retry = useCallback(
    async (messageId: string) => {
      const id = conversationIdRef.current;
      if (!id || streaming) {
        return;
      }
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const events = await streamRetry({
          conversationId: id,
          messageId,
          modelId: effectiveModelId,
          signal: controller.signal,
        });
        await runStream(events, null);
      } catch (caught) {
        if (mountedRef.current) {
          setError({
            code: caught instanceof ApiError ? caught.code : "retry_failed",
            message: caught instanceof Error ? caught.message : "Retry failed.",
            retryable: true,
            messageId,
            retryAfterSeconds: null,
          });
        }
      }
    },
    [effectiveModelId, runStream, streaming],
  );

  const stop = useCallback(async () => {
    const id = conversationIdRef.current;
    const attemptId = attemptRef.current;
    if (!id || !attemptId || stopping) {
      return;
    }
    setStopping(true);
    try {
      await stopGeneration(id, attemptId);
    } catch {
      // The stream still ends; the server closes it either way.
    }
  }, [stopping]);

  const openConversation = useCallback(async (id: string) => {
    conversationIdRef.current = id;
    setCurrentId(id);
    setPendingUser(null);
    setStreamingText("");
    setError(null);
  }, []);

  const newChat = useCallback(() => {
    conversationIdRef.current = null;
    setCurrentId(null);
    setPendingUser(null);
    setStreamingText("");
    setError(null);
  }, []);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: async (_result, id) => {
      if (conversationIdRef.current === id) {
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
    streamingText,
    error,
    streaming,
    stopping,
    hasMore: conversationsQuery.hasNextPage,
    loadingMore: conversationsQuery.isFetchingNextPage,
    models,
    modelId: effectiveModelId,
    selectModel,
    loadMore,
    send,
    retry,
    stop,
    openConversation,
    newChat,
    removeConversation,
  };
}
