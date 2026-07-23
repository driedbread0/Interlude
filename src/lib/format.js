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

export function normalizeDiagnosticText(value) {
  if (!value) return "";

  let text = value;

  if (typeof text === "object") {
    text = text.response || text.output_text || JSON.stringify(text);
  }

  if (typeof text === "string" && text.trim().startsWith("{")) {
    try {
      const parsed = JSON.parse(text);
      text = parsed?.response || parsed?.output_text || text;
    } catch {
      // Older local projects may contain plain prose that begins with a brace.
    }
  }

  return String(text)
    .replace(/\\n/g, "\n")
    .replace(/\\\((.*?)\\\)/gs, "$1")
    .replace(/\\\[(.*?)\\\]/gs, "$1")
    .replace(/\$\$([^$]+)\$\$/gs, "$1")
    .replace(/\$([^$]+)\$/g, "$1")
    .replace(/\\(?:text|mathrm|mathbf|emph)\{([^{}]*)\}/g, "$1")
    .replace(/\\times/g, "x")
    .replace(/\\%/g, "%")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^\*\s+/gm, "• ")
    .replace(/\*([^*]+)\*/g, "$1");
}
