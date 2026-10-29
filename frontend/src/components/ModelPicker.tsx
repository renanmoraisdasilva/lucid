import { useEffect, useId, useRef, useState } from "react";

import type { ModelOption } from "../api/types";

interface ModelPickerProps {
  models: ModelOption[];
  value: string | null;
  disabled?: boolean;
  onChange: (id: string) => void;
}

/** The API labels models as "name · endpoint"; render the two parts separately. */
function splitLabel(option: ModelOption): { name: string; endpoint: string | null } {
  const marker = option.label.lastIndexOf(" \u00b7 ");
  if (marker === -1) {
    return { name: option.label, endpoint: null };
  }
  return {
    name: option.label.slice(0, marker),
    endpoint: option.label.slice(marker + " \u00b7 ".length),
  };
}

export function ModelPicker({ models, value, disabled = false, onChange }: ModelPickerProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);
  const listboxId = useId();

  const selectedIndex = Math.max(
    0,
    models.findIndex((option) => option.id === value),
  );
  const selected = models[selectedIndex];
  const selectedLabel = selected ? splitLabel(selected) : null;

  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    listRef.current?.focus();
    const active = listRef.current?.children[activeIndex];
    if (active instanceof HTMLElement) {
      // jsdom has no layout engine and therefore no scrollIntoView.
      active.scrollIntoView?.({ block: "nearest" });
    }
  }, [open, activeIndex]);

  // Collapse while the picker is disabled (for example, mid-stream) without an
  // effect that would trip the render-phase state rule.
  const [wasDisabled, setWasDisabled] = useState(disabled);
  if (disabled !== wasDisabled) {
    setWasDisabled(disabled);
    if (disabled && open) {
      setOpen(false);
    }
  }

  function openList() {
    setActiveIndex(selectedIndex);
    setOpen(true);
  }

  function closeList(refocus = true) {
    setOpen(false);
    if (refocus) {
      triggerRef.current?.focus();
    }
  }

  function choose(index: number) {
    const option = models[index];
    if (!option) {
      return;
    }
    onChange(option.id);
    closeList();
  }

  function onTriggerKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      openList();
    }
  }

  function onListKeyDown(event: React.KeyboardEvent<HTMLUListElement>) {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setActiveIndex((index) => Math.min(index + 1, models.length - 1));
        break;
      case "ArrowUp":
        event.preventDefault();
        setActiveIndex((index) => Math.max(index - 1, 0));
        break;
      case "Home":
        event.preventDefault();
        setActiveIndex(0);
        break;
      case "End":
        event.preventDefault();
        setActiveIndex(models.length - 1);
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        choose(activeIndex);
        break;
      case "Escape":
        event.preventDefault();
        closeList();
        break;
      case "Tab":
        setOpen(false);
        break;
      default:
        break;
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={`Model: ${selectedLabel?.name ?? "Select model"}${
          selectedLabel?.endpoint ? ` (${selectedLabel.endpoint})` : ""
        }`}
        onClick={() => (open ? closeList(false) : openList())}
        onKeyDown={onTriggerKeyDown}
        className="flex max-w-[10rem] items-center gap-1.5 rounded-full border border-surface-border-subtle bg-transparent py-1 pl-2.5 pr-2 font-mono text-[11px] text-text-secondary transition-colors hover:border-amber-border hover:text-text-primary focus-visible:border-amber-border focus-visible:text-text-primary focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-surface-border-subtle disabled:hover:text-text-secondary sm:max-w-[16rem]"
      >
        <span className="truncate">{selectedLabel?.name ?? "Select model"}</span>
        {selectedLabel?.endpoint ? (
          <span className="shrink-0 text-text-muted">{selectedLabel.endpoint}</span>
        ) : null}
        <svg
          aria-hidden="true"
          viewBox="0 0 12 12"
          className={[
            "h-2.5 w-2.5 shrink-0 text-text-muted transition-transform",
            open ? "rotate-180" : "",
          ].join(" ")}
        >
          <path d="M2 4.5 6 8.5 10 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>

      {open ? (
        <ul
          ref={listRef}
          id={listboxId}
          role="listbox"
          aria-label="Model"
          aria-activedescendant={`${listboxId}-${activeIndex}`}
          tabIndex={-1}
          onKeyDown={onListKeyDown}
          className="absolute bottom-full left-0 z-20 mb-2 w-64 rounded-xl border border-surface-border-subtle bg-surface-elevated p-1 shadow-2xl outline-none"
        >
          {models.map((option, index) => {
            const { name, endpoint } = splitLabel(option);
            const isSelected = index === selectedIndex;
            const isActive = index === activeIndex;
            return (
              <li
                key={option.id}
                id={`${listboxId}-${index}`}
                role="option"
                aria-selected={isSelected}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => choose(index)}
                className={[
                  "flex cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-[12px] transition-colors",
                  isActive ? "bg-surface-hover" : "",
                  isSelected ? "text-text-primary" : "text-text-secondary",
                ].join(" ")}
              >
                <span className="truncate font-mono text-[11px]">{name}</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {endpoint ? (
                    <span className="font-mono text-[10px] text-text-muted">{endpoint}</span>
                  ) : null}
                  <span
                    aria-hidden="true"
                    className={[
                      "w-2.5 text-center text-amber-accent",
                      isSelected ? "opacity-100" : "opacity-0",
                    ].join(" ")}
                  >
                    &#10003;
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
