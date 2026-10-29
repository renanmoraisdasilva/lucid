import { useState } from "react";

import type { ModelOption } from "../api/types";

interface ComposerProps {
  streaming: boolean;
  stopping: boolean;
  models: ModelOption[];
  modelId: string | null;
  onSelectModel: (id: string) => void;
  onSend: (content: string) => void;
  onStop: () => void;
}

const MAX_LENGTH = 16_000;

export function Composer({
  streaming,
  stopping,
  models,
  modelId,
  onSelectModel,
  onSend,
  onStop,
}: ComposerProps) {
  const [draft, setDraft] = useState("");

  function submit() {
    const content = draft.trim();
    if (!content || streaming) {
      return;
    }
    setDraft("");
    onSend(content);
  }

  return (
    <div className="border-t border-surface-border bg-surface-bg px-3 py-4 sm:px-5">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className={[
            "rounded-2xl border border-surface-border-subtle bg-surface-elevated p-3 shadow-2xl transition-colors",
            streaming ? "" : "focus-within:border-amber-border",
          ].join(" ")}
        >
          <label htmlFor="composer" className="sr-only">
            Message Lucid
          </label>
          <textarea
            id="composer"
            rows={1}
            value={draft}
            disabled={streaming}
            maxLength={MAX_LENGTH}
            placeholder={streaming ? "Lucid is responding..." : "Ask anything..."}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                submit();
              }
            }}
            className="min-h-[44px] w-full resize-none bg-transparent text-[14px] leading-relaxed outline-none placeholder:text-text-muted disabled:cursor-not-allowed disabled:opacity-50"
          />

          <div className="flex items-center justify-between gap-2 pt-1">
            <div className="flex min-w-0 items-center gap-2">
              {models.length > 0 ? (
                <>
                  <label htmlFor="model-picker" className="sr-only">
                    Model
                  </label>
                  <select
                    id="model-picker"
                    value={modelId ?? ""}
                    disabled={streaming}
                    onChange={(event) => onSelectModel(event.target.value)}
                    className="max-w-[9rem] truncate rounded-full border border-surface-border-subtle bg-transparent px-2 py-1 font-mono text-[11px] text-text-secondary transition-colors hover:border-amber-border focus:border-amber-border focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 sm:max-w-none"
                  >
                    {models.map((option) => (
                      <option
                        key={option.id}
                        value={option.id}
                        className="bg-surface-elevated text-text-primary"
                      >
                        {option.label}
                      </option>
                    ))}
                  </select>
                </>
              ) : null}

              {streaming ? (
                <span className="flex items-center gap-2 font-mono text-[11px] text-text-muted">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-accent" />
                  {stopping ? "Stopping..." : "Generating response"}
                </span>
              ) : (
                <span className="truncate font-mono text-[11px] text-text-muted">
                  {draft.length > MAX_LENGTH - 1_000
                    ? `${draft.length} / ${MAX_LENGTH}`
                    : "Enter to send \u00b7 Shift + Enter for new line"}
                </span>
              )}
            </div>

            {streaming ? (
              <button
                type="button"
                onClick={onStop}
                disabled={stopping}
                className="flex h-8 items-center gap-1.5 rounded-full border border-amber-border bg-amber-dim px-3 text-[12px] font-medium text-amber-accent transition-colors hover:bg-amber-accent/20 disabled:opacity-50"
              >
                Stop
              </button>
            ) : (
              <button
                type="button"
                onClick={submit}
                disabled={!draft.trim()}
                aria-label="Send message"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-accent text-[#261705] shadow-sm transition-transform hover:bg-amber-hover active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                &rarr;
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
