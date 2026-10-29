import type { ConversationSummary } from "../api/types";

export interface ConversationGroup {
  label: string;
  items: ConversationSummary[];
}

const DAY_MS = 24 * 60 * 60 * 1000;

function startOfDay(value: Date): number {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
}

/**
 * Group conversations by the day they were last updated.
 *
 * Grouping is derived from `updated_at`, the same key as the ordering, so it can
 * never contradict "most recently updated first". A group may span a paginated
 * page boundary; the caller groups the flattened list, not each page.
 */
export function groupConversations(
  items: ConversationSummary[],
  now: Date = new Date(),
): ConversationGroup[] {
  const today = startOfDay(now);
  const buckets: ConversationGroup[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Older", items: [] },
  ];

  for (const item of items) {
    const updated = new Date(item.updated_at);
    const day = startOfDay(updated);
    const difference = Math.round((today - day) / DAY_MS);

    if (difference <= 0) {
      buckets[0].items.push(item);
    } else if (difference === 1) {
      buckets[1].items.push(item);
    } else if (difference <= 7) {
      buckets[2].items.push(item);
    } else {
      buckets[3].items.push(item);
    }
  }

  return buckets.filter((bucket) => bucket.items.length > 0);
}
