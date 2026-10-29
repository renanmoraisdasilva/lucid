import { useEffect, useState } from "react";

function WaitingIndicator() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <span className="text-[13px] text-text-secondary">
      Waiting for the model{seconds > 0 ? ` (${seconds}s)` : ""}
      <span className="animate-pulse">...</span>
    </span>
  );
}

export function StreamingTurn({ text }: { text: string }) {
  return (
    <article className="flex flex-col gap-3" aria-live="polite">
      <header className="flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-full border border-amber-border bg-surface-elevated">
          <span className="h-3.5 w-3.5 animate-pulse rounded-full border border-amber-accent" />
        </span>
        <span className="text-[15px] font-medium">Lucid</span>
        <span className="font-mono text-[11px] text-text-muted">
          {text ? "streaming" : "waiting"}
        </span>
      </header>
      <div className="markdown whitespace-pre-wrap text-[15px] leading-relaxed">
        {text ? (
          <>
            {text}
            <span className="ml-0.5 inline-block h-[1.1em] w-[2px] animate-pulse bg-amber-accent align-[-0.15em]" />
          </>
        ) : (
          <WaitingIndicator />
        )}
      </div>
    </article>
  );
}
