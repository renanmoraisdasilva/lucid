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

export type DashboardRange = "24h" | "7d" | "30d";
export type DashboardBucket = "hour" | "day";

export interface DashboardPricing {
  available: boolean;
  free_tier: boolean;
  input_usd_per_million: number | null;
  output_usd_per_million: number | null;
}

export interface DashboardOverview {
  conversations_active: number;
  conversations_new: number;
  user_messages: number;
  attempts: number;
  completed: number;
  failed: number;
  interrupted: number;
  in_progress: number;
  success_rate: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  average_input_tokens: number | null;
  average_output_tokens: number | null;
  usage_partial: boolean;
  estimated_cost_usd: number | null;
  pricing: DashboardPricing;
}

export interface DashboardTrendPoint {
  bucket_start: string;
  attempts: number;
  completed: number;
  failed: number;
  interrupted: number;
  input_tokens: number | null;
  output_tokens: number | null;
  ttft_ms_p50: number | null;
  ttft_ms_p95: number | null;
  duration_ms_p50: number | null;
  duration_ms_p95: number | null;
}

export interface DashboardLatencyStats {
  p50_ms: number | null;
  p95_ms: number | null;
  samples: number;
}

export interface DashboardLatency {
  ttft: DashboardLatencyStats;
  duration: DashboardLatencyStats;
}

export interface DashboardRecentAttempt {
  attempt_id: string;
  started_at: string;
  conversation_id: string;
  conversation_title: string;
  status: AttemptStatus;
  model: string;
  attempt_no: number;
  retry_count: number;
  input_tokens: number | null;
  output_tokens: number | null;
  ttft_ms: number | null;
  duration_ms: number | null;
  http_status: number | null;
  context_tokens: number | null;
  error_code: string | null;
  error_message: string | null;
}

export interface DashboardData {
  range: DashboardRange;
  generated_at: string;
  bucket: DashboardBucket;
  overview: DashboardOverview;
  trend: DashboardTrendPoint[];
  latency: DashboardLatency;
  recent: DashboardRecentAttempt[];
}
