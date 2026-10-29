export type PickerKeyAction =
  | { kind: "move"; index: number }
  | { kind: "choose" }
  | { kind: "close"; refocus: boolean }
  | { kind: "none" };

/** Map a key pressed inside the listbox to the action the picker should take. */
export function pickerKeyAction(key: string, activeIndex: number, count: number): PickerKeyAction {
  const last = count - 1;

  switch (key) {
    case "ArrowDown":
      return { kind: "move", index: Math.min(activeIndex + 1, last) };
    case "ArrowUp":
      return { kind: "move", index: Math.max(activeIndex - 1, 0) };
    case "Home":
      return { kind: "move", index: 0 };
    case "End":
      return { kind: "move", index: last };
    case "Enter":
    case " ":
      return { kind: "choose" };
    case "Escape":
      return { kind: "close", refocus: true };
    case "Tab":
      return { kind: "close", refocus: false };
    default:
      return { kind: "none" };
  }
}
