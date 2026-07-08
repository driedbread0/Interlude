export function titleCase(value) {
  if (!value) return "";

  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatScore(value) {
  return value === null || value === undefined ? "--" : Number(value).toFixed(3);
}

export function formatPercent(value) {
  return value === null || value === undefined ? "--" : `${Math.round(Number(value) * 100)}%`;
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return "--:--";

  const minutes = Math.floor(seconds / 60);
  const remaining = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remaining}`;
}

export function formatDate(value) {
  if (!value) return "Not analyzed";

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
