import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { stopGeneration, streamChat, streamRetry } from "../../api/client";
import type { StreamEvent } from "../../api/types";
import type { ChatError } from "../../lib/chat-types";
import { isAbortError, toChatError } from "./chat-error";
import { applyEvent, type ChatStreamController } from "./stream-events";

/**
 * Owns the SSE lifecycle for one chat screen.
 *
 * Conversation identity lives in `useChat`; this hook reports new ids through
 * `onConversation` and keeps its own ref for send/retry/stop.
 */
export function useChatStream(options: {
  onConversation: (id: string) => void;
}): ChatStreamController {
  const { onConversation } = options;
  const queryClient = useQueryClient();
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
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

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

  const run = useCallback(
    async (events: AsyncGenerator<StreamEvent>, optimisticText: string | null) => {
      setStreaming(true);
      setStopping(false);
      setError(null);
      setStreamingText("");
      if (optimisticText !== null) {
        setPendingUser(optimisticText);
      }
      attemptRef.current = null;

      let text = "";
      let failed: ChatError | null = null;

      try {
        for await (const event of events) {
          failed =
            applyEvent(event, {
              onMeta: (data) => {
                conversationIdRef.current = data.conversation_id;
                onConversation(data.conversation_id);
                attemptRef.current = data.attempt_id;
              },
              onDelta: (chunk) => {
                text += chunk;
                setStreamingText(text);
              },
            }) ?? failed;
        }
      } catch (caught) {
        if (!isAbortError(caught)) {
          failed = toChatError(caught, "stream_failed", true);
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
    [invalidate, onConversation],
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
          signal: controller.signal,
        });
        await run(events, content);
      } catch (caught) {
        if (mountedRef.current) {
          setError(toChatError(caught, "request_failed", false));
        }
      }
    },
    [run, streaming],
  );

  const retry = useCallback(
    async (messageId: string) => {
      const conversationId = conversationIdRef.current;
      if (!conversationId || streaming) {
        return;
      }
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const events = await streamRetry({
          conversationId,
          messageId,
          signal: controller.signal,
        });
        await run(events, null);
      } catch (caught) {
        if (mountedRef.current) {
          setError(toChatError(caught, "retry_failed", true, messageId));
        }
      }
    },
    [run, streaming],
  );

  const stop = useCallback(async () => {
    const conversationId = conversationIdRef.current;
    const attemptId = attemptRef.current;
    if (!conversationId || !attemptId || stopping) {
      return;
    }
    setStopping(true);
    try {
      await stopGeneration(conversationId, attemptId);
    } catch {
      // The stream still ends; the server closes it either way.
    }
  }, [stopping]);

  const reset = useCallback((conversationId: string | null) => {
    conversationIdRef.current = conversationId;
    attemptRef.current = null;
    setPendingUser(null);
    setStreamingText("");
    setError(null);
  }, []);

  return {
    pendingUser,
    streamingText,
    error,
    streaming,
    stopping,
    send,
    retry,
    stop,
    reset,
  };
}
