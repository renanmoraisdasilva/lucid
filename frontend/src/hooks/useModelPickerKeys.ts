import { useCallback, type KeyboardEvent } from "react";

import { pickerKeyAction } from "../lib/model-picker-keys";

interface ModelPickerKeysOptions {
  activeIndex: number;
  count: number;
  onMove: (index: number) => void;
  onChoose: () => void;
  onClose: (refocus: boolean) => void;
}

/** Keyboard handling for the open model listbox. */
export function useModelPickerKeys(options: ModelPickerKeysOptions) {
  const { activeIndex, count, onMove, onChoose, onClose } = options;

  return useCallback(
    (event: KeyboardEvent<HTMLUListElement>) => {
      const action = pickerKeyAction(event.key, activeIndex, count);
      if (action.kind === "none") {
        return;
      }
      if (action.kind === "move") {
        event.preventDefault();
        onMove(action.index);
      } else if (action.kind === "choose") {
        event.preventDefault();
        onChoose();
      } else {
        if (action.refocus) {
          event.preventDefault();
        }
        onClose(action.refocus);
      }
    },
    [activeIndex, count, onChoose, onClose, onMove],
  );
}
