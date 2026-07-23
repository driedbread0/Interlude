import { useId } from "react";

function fallbackPoints(count = 220) {
  return Array.from({ length: count }, (_, index) => {
    const x = index / Math.max(1, count - 1);
    const envelope = 0.2 + Math.sin(x * Math.PI) * 0.58;
    const movement = Math.sin(index * 0.19) * 0.52 + Math.sin(index * 0.053) * 0.38;

    return {
      x,
      min: -Math.abs(movement * envelope),
      max: Math.abs(movement * envelope),
      rms: Math.abs(movement) * envelope,
    };
  });
}

export default function WaveformCanvas({ points, playhead = 0.28, height = 260, quiet = false, showGrid = true, showPlayhead = true, tone = "light" }) {
  const data = points?.length ? points : fallbackPoints();
  const gradientId = `interlude-wave-${useId().replace(/:/g, "")}`;
  const width = 1000;
  const mid = height / 2;
  const step = width / Math.max(1, data.length - 1);
  const headX = Math.max(0, Math.min(1, playhead)) * width;
  const peak = Math.max(
    0.001,
    ...data.flatMap((point) => [Math.abs(Number(point.max) || 0), Math.abs(Number(point.min) || 0), Math.abs(Number(point.rms) || 0)]),
  );
  const scale = Math.min(1.7, 0.92 / peak);
  const dark = tone === "dark";

  const bars = data.map((point, index) => {
    const x = index * step;
    const top = mid - Math.abs(point.max ?? point.rms ?? 0) * scale * mid * 0.88;
    const bottom = mid + Math.abs(point.min ?? point.rms ?? 0) * scale * mid * 0.88;
    const rms = Math.abs(Number(point.rms) || 0) * scale * mid * 0.88;
    return { x, top, bottom, rmsTop: mid - rms, rmsBottom: mid + rms };
  });

  const upper = bars.map((bar) => `${bar.x.toFixed(1)},${bar.top.toFixed(1)}`).join(" ");
  const lower = [...bars].reverse().map((bar) => `${bar.x.toFixed(1)},${bar.bottom.toFixed(1)}`).join(" ");
  const rmsUpper = bars.map((bar) => `${bar.x.toFixed(1)},${bar.rmsTop.toFixed(1)}`).join(" ");
  const rmsLower = bars.map((bar) => `${bar.x.toFixed(1)},${bar.rmsBottom.toFixed(1)}`).join(" ");

  return (
    <svg className="h-full w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={gradientId} x1="0%" x2="100%" y1="0%" y2="0%">
          <stop offset="0%" stopColor={dark ? "#006C5A" : "#006C5A"} stopOpacity={quiet ? "0.36" : "0.82"} />
          <stop offset="50%" stopColor={dark ? "#24D7B5" : "#00A887"} stopOpacity={quiet ? "0.44" : "0.96"} />
          <stop offset="100%" stopColor={dark ? "#00A887" : "#006C5A"} stopOpacity={quiet ? "0.32" : "0.76"} />
        </linearGradient>
      </defs>

      {showGrid && Array.from({ length: 17 }).map((_, index) => (
        <line
          key={`v-${index}`}
          x1={(index / 16) * width}
          x2={(index / 16) * width}
          y1="0"
          y2={height}
          stroke={dark ? "#A8A096" : "#D8D1C5"}
          strokeWidth="1"
          opacity={index % 4 === 0 ? "0.76" : "0.28"}
        />
      ))}
      {showGrid && Array.from({ length: 5 }).map((_, index) => (
        <line
          key={`h-${index}`}
          x1="0"
          x2={width}
          y1={(index / 4) * height}
          y2={(index / 4) * height}
          stroke={dark ? "#A8A096" : "#D8D1C5"}
          strokeWidth="1"
          opacity="0.42"
        />
      ))}

      <line x1="0" x2={width} y1={mid} y2={mid} stroke={dark ? "#737B85" : "#A8A096"} strokeWidth="1.2" />
      <polygon points={`${upper} ${lower}`} fill={`url(#${gradientId})`} />
      <polyline points={rmsUpper} fill="none" stroke="#006C5A" strokeWidth="1.15" opacity={quiet ? "0.22" : "0.46"} vectorEffect="non-scaling-stroke" />
      <polyline points={rmsLower} fill="none" stroke="#006C5A" strokeWidth="1.15" opacity={quiet ? "0.22" : "0.46"} vectorEffect="non-scaling-stroke" />
      {!quiet && showPlayhead && (
        <>
          <rect x={headX - 2} y="0" width="4" height={height} fill="#082E9B" opacity="0.92" />
          <circle cx={headX} cy={mid} r="8" fill="#FFFDF8" stroke="#082E9B" strokeWidth="3" />
        </>
      )}
    </svg>
  );
}
