import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import type { ModelOption } from "../api/types";
import { useCollapseWhenDisabled } from "../hooks/useCollapseWhenDisabled";
import { useModelPickerKeys } from "../hooks/useModelPickerKeys";
import { splitModelLabel } from "../lib/model-label";
import { ModelPickerList } from "./ModelPickerList";
import { ModelPickerTrigger } from "./ModelPickerTrigger";

interface ModelPickerProps {
  models: ModelOption[];
  value: string | null;
  disabled?: boolean;
  onChange: (id: string) => void;
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
  const label = selected ? splitModelLabel(selected) : null;

  useCollapseWhenDisabled(disabled, () => setOpen(false));

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
    if (option) {
      onChange(option.id);
    }
    closeList();
  }

  function onTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      openList();
    }
  }

  const onListKeyDown = useModelPickerKeys({
    activeIndex,
    count: models.length,
    onMove: setActiveIndex,
    onChoose: () => choose(activeIndex),
    onClose: closeList,
  });

  return (
    <div ref={containerRef} className="relative">
      <ModelPickerTrigger
        triggerRef={triggerRef}
        name={label?.name ?? "Select model"}
        endpoint={label?.endpoint ?? null}
        open={open}
        disabled={disabled}
        listboxId={listboxId}
        onToggle={() => (open ? closeList(false) : openList())}
        onKeyDown={onTriggerKeyDown}
      />

      {open ? (
        <ModelPickerList
          id={listboxId}
          listRef={listRef}
          models={models}
          selectedIndex={selectedIndex}
          activeIndex={activeIndex}
          onActivate={setActiveIndex}
          onChoose={choose}
          onKeyDown={onListKeyDown}
        />
      ) : null}
    </div>
  );
}
