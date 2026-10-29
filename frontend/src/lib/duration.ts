/**
 * Human-readable wait times for rate-limit cooldowns.
 *
 * Provider quotas can be long (a free-tier daily limit returns waits like
 * "11h2m40s"), so a raw second count is not useful in the UI.
 */
export function formatWait(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));

  if (total < 60) {
    return `${total}s`;
  }
  if (total < 3600) {
    return `${Math.floor(total / 60)}m ${total % 60}s`;
  }

  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  return `${hours}h ${minutes}m`;
}
