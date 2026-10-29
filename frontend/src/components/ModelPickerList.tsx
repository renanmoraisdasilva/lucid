import type { KeyboardEvent, RefObject } from "react";

import type { ModelOption } from "../api/types";
import { splitModelLabel } from "../lib/model-label";

interface ModelPickerListProps {
  id: string;
  listRef: RefObject<HTMLUListElement | null>;
  models: ModelOption[];
  selectedIndex: number;
  activeIndex: number;
  onActivate: (index: number) => void;
  onChoose: (index: number) => void;
  onKeyDown: (event: KeyboardEvent<HTMLUListElement>) => void;
}

export function ModelPickerList({
  id,
  listRef,
  models,
  selectedIndex,
  activeIndex,
  onActivate,
  onChoose,
  onKeyDown,
}: ModelPickerListProps) {
  return (
    <ul
      ref={listRef}
      id={id}
      role="listbox"
      aria-label="Model"
      aria-activedescendant={`${id}-${activeIndex}`}
      tabIndex={-1}
      onKeyDown={onKeyDown}
      className="absolute bottom-full left-0 z-20 mb-2 w-64 rounded-xl border border-surface-border-subtle bg-surface-elevated p-1 shadow-2xl outline-none"
    >
      {models.map((option, index) => {
        const { name, endpoint } = splitModelLabel(option);
        const isSelected = index === selectedIndex;
        return (
          <li
            key={option.id}
            id={`${id}-${index}`}
            role="option"
            aria-selected={isSelected}
            onMouseEnter={() => onActivate(index)}
            onClick={() => onChoose(index)}
            className={[
              "flex cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-[12px] transition-colors",
              index === activeIndex ? "bg-surface-hover" : "",
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
  );
}
