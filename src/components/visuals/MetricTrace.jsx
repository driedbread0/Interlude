import { formatScore } from "../../lib/format";

export default function MetricTrace({ title, points, color = "#1F5EFF", inverse = false }) {
  const data = points?.length ? points : [];
  const gradientId = `metric-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  const width = 560;
  const height = 170;
  const pad = { left: 36, right: 12, top: 18, bottom: 28 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const maxX = Math.max(...data.map((point) => point.x), 1);
  const notable = data.length
    ? [...data].sort((a, b) => (inverse ? b.y - a.y : a.y - b.y))[0]
    : null;

  const xFor = (x) => pad.left + (x / maxX) * plotW;
  const yFor = (y) => pad.top + plotH - Math.max(0, Math.min(1, y)) * plotH;
  const path = data
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(point.x).toFixed(1)} ${yFor(point.y).toFixed(1)}`)
    .join(" ");
  const area = data.length
    ? `${path} L ${xFor(data[data.length - 1].x).toFixed(1)} ${height - pad.bottom} L ${xFor(data[0].x).toFixed(1)} ${height - pad.bottom} Z`
    : "";

  return (
    <div className="border border-rule bg-paper p-3">
      <div className="mb-2 flex items-end justify-between gap-3">
        <div>
          <p className="font-display text-lg font-bold text-ink">{title}</p>
          <p className="font-mono text-[10px] text-muted">
            {notable ? `${notable.label} / ${formatScore(notable.y)}` : "no window signal"}
          </p>
        </div>
        <div className="h-5 w-16 border-t-2" style={{ borderColor: color }} />
      </div>

      <svg className="h-36 w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((value) => (
          <g key={value}>
            <line x1={pad.left} x2={width - pad.right} y1={yFor(value)} y2={yFor(value)} stroke="#D5D8DE" />
            <text x="4" y={yFor(value) + 3} className="fill-muted font-mono text-[9px]">
              {value.toFixed(2)}
            </text>
          </g>
        ))}
        {area && <path d={area} fill={`url(#${gradientId})`} />}
        {path && <path d={path} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" />}
        {data.map((point) => (
          <circle
            key={`${point.x}-${point.y}`}
            cx={xFor(point.x)}
            cy={yFor(point.y)}
            r={point === notable ? 5 : 2.6}
            fill={point === notable ? "#111418" : color}
            stroke="#FBF8F0"
            strokeWidth="1.5"
          />
        ))}
        <text x={pad.left} y={height - 8} className="fill-muted font-mono text-[9px]">
          0s
        </text>
        <text x={width - pad.right} y={height - 8} textAnchor="end" className="fill-muted font-mono text-[9px]">
          {Math.round(maxX)}s
        </text>
      </svg>
    </div>
  );
}
