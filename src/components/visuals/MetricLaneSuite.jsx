import { formatScore } from "../../lib/format";

function notablePoint(points, inverse) {
  if (!points?.length) return null;

  return [...points].sort((a, b) => (inverse ? b.y - a.y : a.y - b.y))[0];
}

function LaneTrace({ points, color, inverse, maxX }) {
  const data = points?.length ? points : [];
  const width = 760;
  const height = 56;
  const pad = { left: 6, right: 10, top: 7, bottom: 8 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const notable = notablePoint(data, inverse);

  const xFor = (x) => pad.left + (x / maxX) * plotW;
  const yFor = (y) => pad.top + plotH - Math.max(0, Math.min(1, y)) * plotH;
  const path = data
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(point.x).toFixed(1)} ${yFor(point.y).toFixed(1)}`)
    .join(" ");

  return (
    <svg className="h-14 w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {[0.25, 0.5, 0.75].map((value) => (
        <line
          key={value}
          x1={pad.left}
          x2={width - pad.right}
          y1={yFor(value)}
          y2={yFor(value)}
          stroke="#D5D8DE"
          strokeDasharray="3 5"
          strokeWidth="1"
        />
      ))}
      {Array.from({ length: 13 }).map((_, index) => (
        <line
          key={index}
          x1={pad.left + (index / 12) * plotW}
          x2={pad.left + (index / 12) * plotW}
          y1="0"
          y2={height}
          stroke="#D5D8DE"
          strokeWidth="1"
          opacity={index % 3 === 0 ? 0.74 : 0.32}
        />
      ))}
      {path && <path d={path} fill="none" stroke={color} strokeLinejoin="round" strokeWidth="3" />}
      {data.map((point) => (
        <circle
          key={`${point.x}-${point.y}`}
          cx={xFor(point.x)}
          cy={yFor(point.y)}
          r={point === notable ? 4.4 : 2.2}
          fill={point === notable ? "#111418" : color}
          stroke="#FBF8F0"
          strokeWidth="1.4"
        />
      ))}
      {!data.length && (
        <line
          x1={pad.left}
          x2={width - pad.right}
          y1={height / 2}
          y2={height / 2}
          stroke="#9FA8B5"
          strokeDasharray="6 6"
          strokeWidth="1.3"
        />
      )}
    </svg>
  );
}

export default function MetricLaneSuite({ metrics = [] }) {
  const maxX = Math.max(
    1,
    ...metrics.flatMap((metric) => (metric.points || []).map((point) => Number(point.x) || 0)),
  );

  return (
    <div className="overflow-hidden border-y border-rule-strong bg-paper">
      <div className="grid grid-cols-[minmax(148px,180px)_minmax(220px,1fr)_minmax(96px,116px)] border-b border-rule bg-porcelain/70 px-3 py-2 font-mono text-[10px] uppercase text-muted max-md:grid-cols-[minmax(128px,150px)_1fr_84px] max-sm:grid-cols-[1fr_72px]">
        <span className="min-w-0 truncate">Metric lane</span>
        <span className="signal-ruler min-w-0 max-sm:hidden">
          <span className="bg-porcelain/90 pr-2">Shared analysis clock</span>
        </span>
        <span className="min-w-0 truncate text-right">Focus</span>
      </div>

      <div className="divide-y divide-rule">
        {metrics.map((metric) => {
          const notable = notablePoint(metric.points, metric.inverse);

          return (
            <div
              key={metric.title}
              className="grid grid-cols-[minmax(148px,180px)_minmax(220px,1fr)_minmax(96px,116px)] items-center bg-paper/80 px-3 py-2 transition duration-150 ease-instrument hover:bg-[rgba(79,134,255,0.06)] max-md:grid-cols-[minmax(128px,150px)_1fr_84px] max-sm:grid-cols-1"
            >
              <div className="min-w-0 border-r border-rule pr-3 max-sm:border-r-0 max-sm:pb-2">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 shrink-0" style={{ backgroundColor: metric.color }} />
                  <p className="truncate font-display text-lg font-bold text-ink">{metric.title}</p>
                </div>
                <p className="mt-1 font-mono text-[10px] text-muted">{metric.kind}</p>
              </div>

              <div className="relative min-w-0 px-3 max-sm:px-0">
                <LaneTrace color={metric.color} inverse={metric.inverse} maxX={maxX} points={metric.points} />
              </div>

              <div className="min-w-0 border-l border-rule pl-3 text-right font-mono max-sm:border-l-0 max-sm:border-t max-sm:pt-2 max-sm:text-left">
                <p className="truncate text-[10px] uppercase text-muted">{notable?.label || "no signal"}</p>
                <p className="mt-1 text-base font-bold text-ink">{formatScore(notable?.y)}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-[minmax(148px,180px)_minmax(220px,1fr)_minmax(96px,116px)] border-t border-rule bg-porcelain/60 px-3 py-2 font-mono text-[10px] text-muted max-md:grid-cols-[minmax(128px,150px)_1fr_84px] max-sm:grid-cols-1">
        <span className="min-w-0 truncate">0.00 to 1.00 normalized</span>
        <div className="grid min-w-0 grid-cols-5 max-sm:mt-2">
          {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
            <span key={tick} className={tick === 1 ? "text-right" : tick === 0 ? "text-left" : "text-center"}>
              {Math.round(maxX * tick)}s
            </span>
          ))}
        </div>
        <span className="min-w-0 truncate text-right max-sm:text-left">windowed</span>
      </div>
    </div>
  );
}
