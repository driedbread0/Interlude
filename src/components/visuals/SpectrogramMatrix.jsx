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

function colorFor(value, variant) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));

  if (variant === "chroma") {
    return `rgba(${31 + v * 80}, ${94 + v * 60}, ${255 - v * 24}, ${0.12 + v * 0.78})`;
  }

  return `rgba(${0 + v * 20}, ${168 - v * 30}, ${135 + v * 72}, ${0.10 + v * 0.82})`;
}

export default function SpectrogramMatrix({ rows, variant = "spectrogram", labels, frameless = false }) {
  const matrix = rows?.length ? rows : fallbackRows(variant === "chroma" ? 12 : 48);
  const reversed = [...matrix].reverse();

  return (
    <div className={`relative h-full w-full overflow-hidden bg-paper ${frameless ? "" : "border border-rule"}`}>
      {labels && (
        <div className="absolute bottom-2 left-2 z-10 grid gap-1 font-mono text-[9px] text-muted">
          {labels.slice(0, 6).map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      )}
      <div className="grid h-full w-full gap-px bg-rule/70 p-px">
        {reversed.map((row, rowIndex) => (
          <div
            key={rowIndex}
            className="grid min-h-[3px] gap-px"
            style={{ gridTemplateColumns: `repeat(${row.length}, minmax(0, 1fr))` }}
          >
            {row.map((value, columnIndex) => (
              <span
                key={columnIndex}
                className="block min-h-[3px]"
                style={{ backgroundColor: colorFor(value, variant) }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
