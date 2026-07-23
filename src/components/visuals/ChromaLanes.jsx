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
  return `rgba(${72 + v * 54}, ${45 + v * 38}, ${150 + v * 92}, ${0.06 + v * 0.84})`;
}

export default function ChromaLanes({ rows, labels, duration = 0, transport }) {
  const matrix = rows?.length ? rows : fallbackRows();
  const noteLabels = labels?.length ? labels : ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
  const columns = matrix[0]?.length || 1;
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const inspectionTime = transport?.inspectionTime;
  const inspecting = inspectionTime !== null && inspectionTime !== undefined;
  const activeWindow = transport?.selectedEvidence || transport?.activeWindows?.harmony;
  const activeStart = duration ? Math.max(0, Math.min(1, Number(activeWindow?.start || 0) / duration)) : 0;
  const activeEnd = duration ? Math.max(activeStart, Math.min(1, Number(activeWindow?.end || activeWindow?.start || 0) / duration)) : 0;

  function timeFromEvent(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const plotLeft = 64;
    const plotRight = 12;
    const ratio = (event.clientX - bounds.left - plotLeft) / Math.max(1, bounds.width - plotLeft - plotRight);
    return Math.max(0, Math.min(duration, ratio * duration));
  }

  return (
    <div
      className="chroma-lanes focus-reactive grid h-full grid-rows-[1fr_auto] bg-paper"
      data-focus-stage="chroma"
      data-evidence-metric="harmony"
    >
      <div
        className="relative grid cursor-crosshair gap-1 p-3 pb-2"
        onPointerMove={transport ? (event) => transport.inspectTime(timeFromEvent(event), "harmony") : undefined}
        onPointerLeave={transport ? () => transport.inspectTime(null) : undefined}
        onMouseLeave={transport ? () => transport.inspectTime(null) : undefined}
        onClick={transport ? (event) => transport.seekToTime(timeFromEvent(event)) : undefined}
      >
        {[...matrix].reverse().map((row, rowIndex) => {
          const sourceIndex = matrix.length - rowIndex - 1;
          return (
            <div key={sourceIndex} className="grid grid-cols-[40px_1fr] items-center gap-3">
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
        {transport && (
          <div className="pointer-events-none absolute inset-y-3 left-[64px] right-3">
            {activeWindow && (
              <div
                className={`chroma-active-window ${activeWindow.ambiguous ? "is-ambiguous" : ""}`}
                style={{ left: `${activeStart * 100}%`, width: `${Math.max(0.5, (activeEnd - activeStart) * 100)}%` }}
              />
            )}
            <div
              className={`analysis-live-cursor chroma-cursor ${inspecting ? "is-inspecting" : ""}`}
              style={inspecting ? { left: `${Math.max(0, Math.min(1, inspectionTime / Math.max(1, duration))) * 100}%` } : undefined}
            />
          </div>
        )}
      </div>
      <div className="ml-[64px] mr-3 grid border-t border-rule py-2 font-mono text-[10px] text-muted" style={{ gridTemplateColumns: `repeat(${ticks.length}, 1fr)` }}>
        {ticks.map((tick, index) => (
          <span key={tick} className={index === ticks.length - 1 ? "text-right" : index === 0 ? "text-left" : "text-center"}>
            {formatDuration((duration || 0) * tick)}
          </span>
        ))}
      </div>
    </div>
  );
}
