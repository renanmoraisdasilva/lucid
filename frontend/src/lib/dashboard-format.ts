import type { DashboardRange } from "../api/types";

export const DASHBOARD_REFRESH_MS = 20_000;

export const RANGE_LABELS: Record<DashboardRange, string> = {
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
  "30d": "Last 30 days",
};

export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatTokens(value: number | null): string {
  if (value === null) {
    return "—";
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}k`;
  }
  return String(value);
}

export function formatPercent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function formatCost(value: number | null): string {
  return value === null ? "Unavailable" : `$${value.toFixed(2)}`;
}

export function formatUpdated(updatedAt: number, now: number): string {
  if (updatedAt <= 0) {
    return "Not loaded yet";
  }
  const seconds = Math.max(0, Math.floor((now - updatedAt) / 1000));
  if (seconds < 5) {
    return "Updated just now";
  }
  if (seconds < 60) {
    return `Updated ${seconds}s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `Updated ${minutes}m ago`;
  }
  return `Updated ${Math.floor(minutes / 60)}h ago`;
}
