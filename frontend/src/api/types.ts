export interface ModelsResponse {
  items: ModelOption[];
  default_id: string;
}

export interface ModelOption {
  id: string;
  label: string;
  provider: string;
  model: string;
}

export type AttemptStatus = "in_progress" | "completed" | "failed" | "interrupted";

export type Role = "user" | "assistant";

export interface Usage {
  input_tokens: number | null;
  output_tokens: number | null;
  thought_tokens: number | null;
  total_tokens: number | null;
}

export interface AttemptSummary {
  id: string;
  status: AttemptStatus;
  model: string;
  attempt_no: number;
  retryable: boolean;
  error_code: string | null;
  error_message: string | null;
  usage: Usage | null;
}

export interface Message {
  id: string;
  role: Role;
  seq: number;
  content: string;
  created_at: string;
  attempt: AttemptSummary | null;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  active_attempt_id: string | null;
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[];
}

export interface ConversationListResponse {
  items: ConversationSummary[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface MetaEvent {
  conversation_id: string;
  conversation_title: string;
  user_message_id: string;
  attempt_id: string;
  model: string;
  is_new_conversation: boolean;
}

export interface DoneEvent {
  attempt_id: string;
  status: Extract<AttemptStatus, "completed" | "interrupted">;
  assistant_message_id: string | null;
  finish_reason: string;
}

export interface ErrorEvent {
  code: string;
  message: string;
  retryable: boolean;
  attempt_id: string;
  retry_after_seconds?: number | null;
  assistant_message_id?: string | null;
}

export type StreamEvent =
  | { type: "meta"; data: MetaEvent }
  | { type: "delta"; data: { text: string } }
  | { type: "usage"; data: Usage }
  | { type: "done"; data: DoneEvent }
  | { type: "error"; data: ErrorEvent };
