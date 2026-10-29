import { useState } from "react";

/**
 * Run `onDisabled` when `disabled` flips to true, during render rather than in an
 * effect so the UI collapses in the same commit (no flash of a dead control).
 */
export function useCollapseWhenDisabled(disabled: boolean, onDisabled: () => void): void {
  const [wasDisabled, setWasDisabled] = useState(disabled);
  if (disabled === wasDisabled) {
    return;
  }
  setWasDisabled(disabled);
  if (disabled) {
    onDisabled();
  }
}
