import type { Message } from "../../api/types";
import { Markdown } from "../Markdown";

function UsageLine({ message }: { message: Message }) {
  const usage = message.attempt?.usage ?? null;
  if (usage === null || (usage.input_tokens === null && usage.output_tokens === null)) {
    return <span className="font-mono text-[11px] text-text-muted">usage unavailable</span>;
  }
  return (
    <span className="font-mono text-[11px] text-text-muted">
      {usage.input_tokens ?? "?"} in &middot; {usage.output_tokens ?? "?"} out
    </span>
  );
}

export function AssistantTurn({ message }: { message: Message }) {
  return (
    <article className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-full border border-amber-border bg-surface-elevated">
          <span className="h-3.5 w-3.5 rounded-full border border-amber-accent" />
        </span>
        <span className="text-[15px] font-medium">Lucid</span>
        <UsageLine message={message} />
        {message.attempt?.status === "interrupted" ? (
          <span className="rounded-full border border-amber-border bg-amber-dim px-2 py-0.5 text-[11px] font-medium text-amber-accent">
            Interrupted
          </span>
        ) : null}
        {message.attempt?.status === "failed" ? (
          <span className="rounded-full border border-danger-border bg-danger-dim px-2 py-0.5 text-[11px] font-medium text-danger">
            Failed
          </span>
        ) : null}
      </header>
      <Markdown content={message.content} />
    </article>
  );
}
