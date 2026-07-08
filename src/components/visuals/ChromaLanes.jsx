import { formatDuration } from "../../lib/format";

function fallbackRows(rows = 12, columns = 120) {
  return Array.from({ length: rows }, (_, row) =>
    Array.from({ length: columns }, (_, column) => {
      const movement = Math.sin(column * 0.12 + row * 0.65) * 0.35 + 0.45;
      const emphasis = row % 3 === 0 ? 0.24 : 0;
      return Math.max(0, Math.min(1, movement + emphasis));
    }),
  );
}

function color(value) {
  const v = Math.max(0, Math.min(1, Number(value) || 0));
  return `rgba(${31 + v * 28}, ${94 + v * 74}, ${255 - v * 72}, ${0.08 + v * 0.82})`;
}

export default function ChromaLanes({ rows, labels, duration = 0 }) {
  const matrix = rows?.length ? rows : fallbackRows();
  const noteLabels = labels?.length ? labels : ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
  const columns = matrix[0]?.length || 1;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="grid h-full grid-rows-[1fr_auto] border border-rule bg-paper">
      <div className="grid gap-1 p-3 pb-2">
        {[...matrix].reverse().map((row, rowIndex) => {
          const sourceIndex = matrix.length - rowIndex - 1;
          return (
            <div key={sourceIndex} className="grid grid-cols-[34px_1fr] items-center gap-2">
              <span className="font-mono text-[10px] text-muted">{noteLabels[sourceIndex]}</span>
              <div
                className="grid h-3 overflow-hidden bg-porcelain"
                style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
              >
                {row.map((value, columnIndex) => (
                  <span
                    key={columnIndex}
                    className="block h-full"
                    style={{ backgroundColor: color(value) }}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      <div className="ml-[54px] mr-3 grid border-t border-rule py-2 font-mono text-[10px] text-muted" style={{ gridTemplateColumns: `repeat(${ticks.length}, 1fr)` }}>
        {ticks.map((tick, index) => (
          <span key={tick} className={index === ticks.length - 1 ? "text-right" : index === 0 ? "text-left" : "text-center"}>
            {formatDuration((duration || 0) * tick)}
          </span>
        ))}
      </div>
    </div>
  );
}
