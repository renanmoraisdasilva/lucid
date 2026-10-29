export interface ChatError {
  code: string;
  message: string;
  retryable: boolean;
  messageId: string | null;
  retryAfterSeconds: number | null;
}
