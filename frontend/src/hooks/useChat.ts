import { useCallback, useEffect, useRef, useState } from "react";

import {
  ApiError,
  deleteConversation,
  getConversation,
  listConversations,
  stopGeneration,
  streamChat,
  streamRetry,
} from "../api/client";
import type { ConversationSummary, Message, StreamEvent, Usage } from "../api/types";

export interface ChatError {
  code: string;
  message: string;
  retryable: boolean;
  messageId: string | null;
}

export interface UseChat {
  conversations: ConversationSummary[];
  currentId: string | null;
  messages: Message[];
  streamingText: string;
  usage: Usage | null;
  error: ChatError | null;
  streaming: boolean;
  stopping: boolean;
  send: (content: string) => Promise<void>;
  retry: (messageId: string) => Promise<void>;
  stop: () => Promise<void>;
  openConversation: (id: string) => Promise<void>;
  newChat: () => void;
  removeConversation: (id: string) => Promise<void>;
}

export function useChat(): UseChat {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [stopping, setStopping] = useState(false);

  const attemptRef = useRef<string | null>(null);
  const conversationRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const page = await listConversations();
      if (mountedRef.current) {
        setConversations(page.items);
      }
    } catch {
      // The sidebar is not worth an error banner; the thread shows failures.
    }
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    const detail = await getConversation(id);
    if (!mountedRef.current) {
      return;
    }
    setCurrentId(detail.id);
    conversationRef.current = detail.id;
    setMessages(detail.messages);
    setStreamingText("");
    setError(null);
    setUsage(null);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listConversations(controller.signal)
      .then((page) => {
        if (!controller.signal.aborted) {
          setConversations(page.items);
        }
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const runStream = useCallback(
    async (events: AsyncGenerator<StreamEvent>, optimisticUserText: string) => {
      setStreaming(true);
      setStopping(false);
      setError(null);
      setUsage(null);
      setStreamingText("");
      attemptRef.current = null;

      const optimistic: Message = {
        id: `optimistic-${Date.now()}`,
        role: "user",
        seq: Number.MAX_SAFE_INTEGER,
        content: optimisticUserText,
        created_at: new Date().toISOString(),
        attempt: null,
      };
      setMessages((previous) => [...previous, optimistic]);

      let text = "";
      let failed: ChatError | null = null;

      try {
        for await (const event of events) {
          if (event.type === "meta") {
            setCurrentId(event.data.conversation_id);
            conversationRef.current = event.data.conversation_id;
            attemptRef.current = event.data.attempt_id;
          } else if (event.type === "delta") {
            text += event.data.text;
            setStreamingText(text);
          } else if (event.type === "usage") {
            setUsage(event.data);
          } else if (event.type === "error") {
            failed = {
              code: event.data.code,
              message: event.data.message,
              retryable: event.data.retryable,
              messageId: null,
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
          };
        }
      } finally {
        if (mountedRef.current) {
          setStreaming(false);
          setStopping(false);
          setStreamingText("");
          attemptRef.current = null;
        }
      }

      if (!mountedRef.current) {
        return;
      }

      const id = conversationRef.current;
      if (id) {
        try {
          await loadConversation(id);
        } catch {
          // Keep whatever is on screen; the next action retries the fetch.
        }
      }
      await refreshConversations();

      if (failed) {
        setError(failed);
      }
    },
    [loadConversation, refreshConversations],
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
          conversationId: currentId,
          content,
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
          });
        }
      }
    },
    [currentId, runStream, streaming],
  );

  const retry = useCallback(
    async (messageId: string) => {
      const id = conversationRef.current;
      if (!id || streaming) {
        return;
      }
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const events = await streamRetry({
          conversationId: id,
          messageId,
          signal: controller.signal,
        });
        await runStream(events, "");
      } catch (caught) {
        if (mountedRef.current) {
          setError({
            code: caught instanceof ApiError ? caught.code : "retry_failed",
            message: caught instanceof Error ? caught.message : "Retry failed.",
            retryable: true,
            messageId,
          });
        }
      }
    },
    [runStream, streaming],
  );

  const stop = useCallback(async () => {
    const id = conversationRef.current;
    const attemptId = attemptRef.current;
    if (!id || !attemptId || stopping) {
      return;
    }
    setStopping(true);
    try {
      await stopGeneration(id, attemptId);
    } catch {
      // The stream will still end; the server closes it either way.
    }
  }, [stopping]);

  const openConversation = useCallback(
    async (id: string) => {
      setError(null);
      await loadConversation(id);
    },
    [loadConversation],
  );

  const newChat = useCallback(() => {
    setCurrentId(null);
    conversationRef.current = null;
    setMessages([]);
    setStreamingText("");
    setUsage(null);
    setError(null);
  }, []);

  const removeConversation = useCallback(
    async (id: string) => {
      await deleteConversation(id);
      if (conversationRef.current === id) {
        newChat();
      }
      await refreshConversations();
    },
    [newChat, refreshConversations],
  );

  return {
    conversations,
    currentId,
    messages,
    streamingText,
    usage,
    error,
    streaming,
    stopping,
    send,
    retry,
    stop,
    openConversation,
    newChat,
    removeConversation,
  };
}
