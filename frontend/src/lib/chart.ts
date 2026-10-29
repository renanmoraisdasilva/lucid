export interface SegmentPoint {
  index: number;
  value: number;
}

const NICE_FRACTIONS = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];

/** Round a maximum up to a readable axis value. */
export function niceMax(value: number): number {
  if (!Number.isFinite(value) || value <= 0) {
    return 1;
  }
  const exponent = Math.floor(Math.log10(value));
  const magnitude = 10 ** exponent;
  const fraction = value / magnitude;
  const nice = NICE_FRACTIONS.find((candidate) => fraction <= candidate) ?? 10;
  return nice * magnitude;
}

export function axisTicks(max: number, count = 4): number[] {
  return Array.from({ length: count + 1 }, (_, index) => (max / count) * index);
}

export function xPercent(index: number, count: number): number {
  if (count <= 1) {
    return 50;
  }
  return (index / (count - 1)) * 100;
}

export function yPercent(value: number, max: number): number {
  if (max <= 0) {
    return 100;
  }
  return 100 - Math.min(1, Math.max(0, value / max)) * 100;
}

/** Split a series into runs of non-null values, so gaps stay empty. */
export function buildSegments<T>(items: T[], value: (item: T) => number | null): SegmentPoint[][] {
  const segments: SegmentPoint[][] = [];
  let current: SegmentPoint[] = [];
  items.forEach((item, index) => {
    const point = value(item);
    if (point === null) {
      if (current.length > 0) {
        segments.push(current);
        current = [];
      }
      return;
    }
    current.push({ index, value: point });
  });
  if (current.length > 0) {
    segments.push(current);
  }
  return segments;
}

export function buildLinePath(segment: SegmentPoint[], count: number, max: number): string {
  if (segment.length === 0) {
    return "";
  }
  if (segment.length === 1) {
    const x = xPercent(segment[0].index, count);
    const y = yPercent(segment[0].value, max);
    return `M ${(x - 0.35).toFixed(2)} ${y.toFixed(2)} L ${(x + 0.35).toFixed(2)} ${y.toFixed(2)}`;
  }
  return segment
    .map((point, index) => {
      const command = index === 0 ? "M" : "L";
      return `${command} ${xPercent(point.index, count).toFixed(2)} ${yPercent(point.value, max).toFixed(2)}`;
    })
    .join(" ");
}

export function buildAreaPath(segment: SegmentPoint[], count: number, max: number): string {
  if (segment.length === 0) {
    return "";
  }
  const first = xPercent(segment[0].index, count);
  const last = xPercent(segment[segment.length - 1].index, count);
  const points = segment
    .map(
      (point) =>
        `${xPercent(point.index, count).toFixed(2)} ${yPercent(point.value, max).toFixed(2)}`,
    )
    .join(" L ");
  return `M ${first.toFixed(2)} 100 L ${points} L ${last.toFixed(2)} 100 Z`;
}

/** Pick at most `maxLabels` indices, always including the ends. */
export function selectedIndices(total: number, maxLabels = 7): number[] {
  if (total <= 0) {
    return [];
  }
  if (total <= maxLabels) {
    return Array.from({ length: total }, (_, index) => index);
  }
  const step = Math.ceil((total - 1) / (maxLabels - 1));
  const indices = new Set<number>();
  for (let index = 0; index < total; index += step) {
    indices.add(index);
  }
  indices.add(total - 1);
  return [...indices].sort((left, right) => left - right);
}

export function seriesMax(values: Array<number | null>): number {
  const max = Math.max(0, ...values.filter((value): value is number => value !== null));
  return niceMax(max || 1);
}
