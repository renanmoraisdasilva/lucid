import { describe, expect, it } from "vitest";

import type { ConversationSummary } from "../api/types";
import { groupConversations } from "./grouping";

function conversation(id: string, updatedAt: string): ConversationSummary {
  return {
    id,
    title: id,
    created_at: updatedAt,
    updated_at: updatedAt,
    active_attempt_id: null,
  };
}

const NOW = new Date("2026-10-29T12:00:00Z");

describe("groupConversations", () => {
  it("groups by updated day relative to now", () => {
    const groups = groupConversations(
      [
        conversation("today", "2026-10-29T09:00:00Z"),
        conversation("yesterday", "2026-10-28T09:00:00Z"),
        conversation("week", "2026-10-25T09:00:00Z"),
        conversation("older", "2026-10-01T09:00:00Z"),
      ],
      NOW,
    );

    expect(groups.map((group) => group.label)).toEqual([
      "Today",
      "Yesterday",
      "Previous 7 days",
      "Older",
    ]);
    expect(groups[0].items.map((item) => item.id)).toEqual(["today"]);
  });

  it("omits empty groups", () => {
    const groups = groupConversations([conversation("today", "2026-10-29T09:00:00Z")], NOW);

    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe("Today");
  });

  it("preserves the incoming order inside a group", () => {
    const groups = groupConversations(
      [conversation("a", "2026-10-29T11:00:00Z"), conversation("b", "2026-10-29T10:00:00Z")],
      NOW,
    );

    expect(groups[0].items.map((item) => item.id)).toEqual(["a", "b"]);
  });

  it("returns nothing for an empty list", () => {
    expect(groupConversations([], NOW)).toEqual([]);
  });
});
