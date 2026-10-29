import type { ModelOption } from "../api/types";

/** Split the API's "name \u00b7 endpoint" label into the two parts the UI shows. */
export function splitModelLabel(option: ModelOption): {
  name: string;
  endpoint: string | null;
} {
  const marker = option.label.lastIndexOf(" \u00b7 ");
  if (marker === -1) {
    return { name: option.label, endpoint: null };
  }
  return {
    name: option.label.slice(0, marker),
    endpoint: option.label.slice(marker + " \u00b7 ".length),
  };
}
