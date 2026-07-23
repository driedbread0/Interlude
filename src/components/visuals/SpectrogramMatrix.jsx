function fallbackRows(rows = 48, columns = 110) {
  return Array.from({ length: rows }, (_, row) =>
    Array.from({ length: columns }, (_, column) => {
      const band = Math.exp(-Math.abs(row - rows * 0.3) / (rows * 0.34));
      const pulse = Math.sin(column * 0.18 + row * 0.26) * 0.35 + 0.5;
      const transient = column % 17 < 2 ? 0.26 : 0;
      return Math.max(0, Math.min(1, band * pulse + transient));
    }),
  );
}

function colorFor(value, variant, tone) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));

  if (variant === "chroma") {
    return `rgba(${31 + v * 80}, ${94 + v * 60}, ${255 - v * 24}, ${0.12 + v * 0.78})`;
  }

  if (tone === "dark") {
    const red = Math.round(168 - v * 138);
    const green = Math.round(160 + v * 46);
    const blue = Math.round(150 + v * 16);
    return `rgba(${red}, ${green}, ${blue}, ${0.12 + v * 0.80})`;
  }

  return `rgba(${0 + v * 20}, ${168 - v * 30}, ${135 + v * 72}, ${0.10 + v * 0.82})`;
}

export default function SpectrogramMatrix({ rows, variant = "spectrogram", labels, frameless = false, tone = "light" }) {
  const matrix = rows?.length ? rows : fallbackRows(variant === "chroma" ? 12 : 48);
  const reversed = [...matrix].reverse();

  return (
    <div className={`relative h-full w-full overflow-hidden ${tone === "dark" ? "bg-signal-ink" : "bg-paper"} ${frameless ? "" : "border border-rule"}`}>
      {labels && (
        <div className="absolute bottom-2 left-2 z-10 grid gap-1 font-mono text-[9px] text-muted">
          {labels.slice(0, 6).map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      )}
      <div className={`grid h-full w-full ${tone === "dark" ? "bg-signal-ink" : "bg-rule/40"}`}>
        {reversed.map((row, rowIndex) => (
          <div
            key={rowIndex}
            className="grid min-h-[3px]"
            style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}
          >
            {row.map((value, columnIndex) => (
              <span
                key={columnIndex}
                className="block min-h-[3px]"
                style={{ backgroundColor: colorFor(value, variant, tone) }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
