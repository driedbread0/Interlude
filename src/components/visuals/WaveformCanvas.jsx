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

export default function WaveformCanvas({ points, playhead = 0.28, height = 260, quiet = false, showPlayhead = true }) {
  const data = points?.length ? points : fallbackPoints();
  const width = 1000;
  const mid = height / 2;
  const step = width / Math.max(1, data.length - 1);
  const headX = Math.max(0, Math.min(1, playhead)) * width;

  const bars = data.map((point, index) => {
    const x = index * step;
    const top = mid - Math.abs(point.max ?? point.rms ?? 0) * mid * 0.86;
    const bottom = mid + Math.abs(point.min ?? point.rms ?? 0) * mid * 0.86;
    return { x, top, bottom };
  });

  const upper = bars.map((bar) => `${bar.x.toFixed(1)},${bar.top.toFixed(1)}`).join(" ");
  const lower = [...bars].reverse().map((bar) => `${bar.x.toFixed(1)},${bar.bottom.toFixed(1)}`).join(" ");

  return (
    <svg className="h-full w-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="interlude-wave" x1="0%" x2="100%" y1="0%" y2="0%">
          <stop offset="0%" stopColor="#1F5EFF" stopOpacity={quiet ? "0.42" : "0.92"} />
          <stop offset="48%" stopColor="#00A887" stopOpacity={quiet ? "0.46" : "0.86"} />
          <stop offset="100%" stopColor="#6E3FF2" stopOpacity={quiet ? "0.28" : "0.52"} />
        </linearGradient>
      </defs>

      {Array.from({ length: 13 }).map((_, index) => (
        <line
          key={`v-${index}`}
          x1={(index / 12) * width}
          x2={(index / 12) * width}
          y1="0"
          y2={height}
          stroke="#D5D8DE"
          strokeWidth="1"
          opacity="0.7"
        />
      ))}
      {Array.from({ length: 5 }).map((_, index) => (
        <line
          key={`h-${index}`}
          x1="0"
          x2={width}
          y1={(index / 4) * height}
          y2={(index / 4) * height}
          stroke="#D5D8DE"
          strokeWidth="1"
          opacity="0.42"
        />
      ))}

      <line x1="0" x2={width} y1={mid} y2={mid} stroke="#9FA8B5" strokeWidth="1.2" />
      <polygon points={`${upper} ${lower}`} fill="url(#interlude-wave)" />
      {!quiet && showPlayhead && (
        <>
          <rect x={headX - 2} y="0" width="4" height={height} fill="#082E9B" opacity="0.92" />
          <circle cx={headX} cy={mid} r="8" fill="#FBF8F0" stroke="#082E9B" strokeWidth="3" />
        </>
      )}
    </svg>
  );
}
