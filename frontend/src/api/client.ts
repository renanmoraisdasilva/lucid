import { parseSseFrames } from "./sse";
import type {
  ConversationDetail,
  ConversationListResponse,
  DashboardData,
  DashboardRange,
  StreamEvent,
} from "./types";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
    };
    return new ApiError(
      body.error?.code ?? "request_failed",
      body.error?.message ?? "The request failed.",
      response.status,
    );
  } catch {
    return new ApiError("request_failed", "The request failed.", response.status);
  }
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as T;
}

export function listConversations(
  cursor?: string | null,
  signal?: AbortSignal,
): Promise<ConversationListResponse> {
  const params = new URLSearchParams({ limit: "20" });
  if (cursor) {
    params.set("cursor", cursor);
  }
  return requestJson<ConversationListResponse>(`/api/conversations?${params.toString()}`, {
    signal,
  });
}

export function getConversation(id: string, signal?: AbortSignal): Promise<ConversationDetail> {
  return requestJson<ConversationDetail>(`/api/conversations/${id}`, { signal });
}

export function getDashboard(range: DashboardRange, signal?: AbortSignal): Promise<DashboardData> {
  const params = new URLSearchParams({ range });
  return requestJson<DashboardData>(`/api/dashboard?${params.toString()}`, { signal });
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
  if (!response.ok && response.status !== 404) {
    throw await toApiError(response);
  }
}

export async function stopGeneration(conversationId: string, attemptId: string): Promise<void> {
  const response = await fetch(
    `/api/conversations/${conversationId}/generations/${attemptId}/stop`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw await toApiError(response);
  }
}

async function streamResponse(
  input: string,
  init: RequestInit,
): Promise<AsyncGenerator<StreamEvent>> {
  const response = await fetch(input, init);
  if (!response.ok || !response.body) {
    throw await toApiError(response);
  }
  return parseSseFrames(response.body);
}

export function streamChat(options: {
  conversationId: string | null;
  content: string;
  signal?: AbortSignal;
}): Promise<AsyncGenerator<StreamEvent>> {
  return streamResponse("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: options.conversationId,
      content: options.content,
    }),
    signal: options.signal,
  });
}

export function streamRetry(options: {
  conversationId: string;
  messageId: string;
  signal?: AbortSignal;
}): Promise<AsyncGenerator<StreamEvent>> {
  return streamResponse(
    `/api/conversations/${options.conversationId}/messages/${options.messageId}/retry`,
    { method: "POST", signal: options.signal },
  );
}
