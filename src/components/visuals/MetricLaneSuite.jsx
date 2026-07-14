import { useState } from "react";
import { formatScore } from "../../lib/format";

const HOVER_FILL = "rgba(79, 134, 255, 0.18)";
const HOVER_STROKE = "#4F86FF";
const LOCK_FILL = "rgba(0, 71, 255, 0.76)";
const LOCK_STROKE = "#0047FF";
const ACTIVE_LINE_HALO = "rgba(251, 248, 240, 0.94)";

function clamp(value, min, max) {
  const low = Math.min(min, max);
  const high = Math.max(min, max);
  return Math.max(low, Math.min(high, value));
}

function asNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function omitKey(source, key) {
  const next = { ...source };
  delete next[key];
  return next;
}

function normalizePoints(points, maxX) {
  const sorted = (points || [])
    .filter((point) => Number.isFinite(Number(point?.y)))
    .map((point) => {
      const fallbackX = asNumber(point.x, 0);
      return {
        ...point,
        x: fallbackX,
        y: clamp(asNumber(point.y, 0), 0, 1),
        start: asNumber(point.start, fallbackX),
        end: asNumber(point.end, fallbackX),
      };
    })
    .sort((a, b) => a.start - b.start);

  return sorted.map((point, index) => {
    const nextStart = sorted[index + 1]?.start;
    const start = clamp(point.start, 0, maxX);
    let end = clamp(point.end, 0, maxX);

    if (end <= start) {
      const fallbackSpan = Math.max(maxX * 0.015, maxX / Math.max(12, sorted.length * 1.6));
      end = Number.isFinite(nextStart) && nextStart > start ? nextStart : start + fallbackSpan;
    }

    end = clamp(end, start + maxX * 0.004, maxX);

    return {
      ...point,
      __key: `${point.label || "window"}-${start.toFixed(3)}-${end.toFixed(3)}-${index}`,
      __start: start,
      __end: end,
      __mid: (start + end) / 2,
    };
  });
}

function buildPath(data, xFor, yFor) {
  return data
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xFor(point.__mid).toFixed(1)} ${yFor(point.y).toFixed(1)}`)
    .join(" ");
}

function LaneTrace({
  activeKey,
  color,
  cursorTime,
  data,
  emptyLabel,
  lockedKey,
  maxX,
  metricKey,
  onClearHover,
  onClearCursor,
  onCursorMove,
  onHover,
  onToggleLock,
}) {
  const width = 760;
  const height = 112;
  const pad = { left: 6, right: 10, top: 48, bottom: 8 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const activePoint = data.find((point) => point.__key === activeKey);
  const locked = Boolean(lockedKey && activePoint?.__key === lockedKey);
  const zooming = cursorTime !== null && cursorTime !== undefined;
  const activeClipId = `active-line-${metricKey.replace(/[^a-zA-Z0-9_-]/g, "-")}`;

  const baseXFor = (x) => pad.left + (x / maxX) * plotW;
  const xFor = (x) => {
    const baseX = baseXFor(x);

    if (!zooming) {
      return baseX;
    }

    const cursorX = baseXFor(cursorTime);
    const distance = baseX - cursorX;
    const radius = plotW * 0.075;
    const cutoff = radius * 2.05;

    if (Math.abs(distance) > cutoff) {
      return baseX;
    }

    const normalizedDistance = Math.abs(distance) / cutoff;
    const influence = (1 - normalizedDistance) ** 3;
    const magnifiedX = cursorX + distance * (1 + influence * 3.45);

    return clamp(magnifiedX, pad.left, width - pad.right);
  };
  const yFor = (y) => pad.top + plotH - clamp(y, 0, 1) * plotH;
  const path = buildPath(data, xFor, yFor);
  const activeX = activePoint ? xFor(activePoint.__start) : 0;
  const activeWidth = activePoint ? Math.max(4, xFor(activePoint.__end) - activeX) : 0;

  function handleMouseMove(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const relativeX = ((event.clientX - bounds.left) / bounds.width) * width;
    const time = clamp(((relativeX - pad.left) / plotW) * maxX, 0, maxX);
    onCursorMove(metricKey, time);
  }

  return (
    <svg
      className="h-24 w-full outline-none"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      onMouseMove={handleMouseMove}
      onMouseLeave={() => {
        onClearCursor(metricKey);
        if (!lockedKey) onClearHover(metricKey);
      }}
    >
      <defs>
        {activePoint && (
          <clipPath id={activeClipId}>
            <rect x={activeX} y={pad.top - 8} width={activeWidth} height={plotH + 16} />
          </clipPath>
        )}
      </defs>

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
          y1={pad.top - 10}
          y2={height - pad.bottom + 2}
          stroke="#D5D8DE"
          strokeWidth="1"
          opacity={index % 3 === 0 ? 0.74 : 0.32}
        />
      ))}

      {activePoint && (
        <g pointerEvents="none">
          <rect
            x={activeX}
            y={pad.top - 6}
            width={activeWidth}
            height={plotH + 12}
            fill={locked ? LOCK_FILL : HOVER_FILL}
            stroke={locked ? LOCK_STROKE : HOVER_STROKE}
            strokeDasharray={locked ? undefined : "4 3"}
            strokeWidth={locked ? 2 : 1.2}
          />
          <text
            x={activeX + 5}
            y={pad.top - 10}
            fill={locked ? LOCK_STROKE : "#082E9B"}
            fontFamily="IBM Plex Mono"
            fontSize="9"
          >
            {locked ? "locked region" : "detected region"}
          </text>
        </g>
      )}

      {path && <path d={path} fill="none" stroke={color} strokeLinejoin="round" strokeWidth="3" />}
      {activePoint && path && (
        <path
          d={path}
          clipPath={`url(#${activeClipId})`}
          fill="none"
          stroke={ACTIVE_LINE_HALO}
          strokeLinejoin="round"
          strokeWidth="7"
          strokeLinecap="round"
        />
      )}
      {activePoint && path && (
        <path
          d={path}
          clipPath={`url(#${activeClipId})`}
          fill="none"
          stroke={color}
          strokeLinejoin="round"
          strokeWidth="4.4"
          strokeLinecap="round"
        />
      )}
      {data.map((point) => {
        const pointActive = point.__key === activeKey;

        return (
          <circle
            key={`${point.__key}-dot`}
            cx={xFor(point.__mid)}
            cy={yFor(point.y)}
            r={pointActive ? 4.6 : 2.4}
            fill={pointActive ? color : color}
            stroke={pointActive && locked ? LOCK_STROKE : "#FBF8F0"}
            strokeWidth={pointActive ? 1.8 : 1.4}
          />
        );
      })}

      {!data.length && (
        <>
          <line
            x1={pad.left}
            x2={width - pad.right}
            y1={pad.top + plotH / 2}
            y2={pad.top + plotH / 2}
            stroke="#9FA8B5"
            strokeDasharray="6 6"
            strokeWidth="1.3"
          />
          <text x={pad.left + 8} y={pad.top + plotH / 2 - 6} fill="#737B85" fontFamily="IBM Plex Mono" fontSize="9">
            {emptyLabel || "no usable windows"}
          </text>
        </>
      )}

      {data.map((point) => {
        const isLockedElsewhere = Boolean(lockedKey && lockedKey !== point.__key);
        const hitX = baseXFor(point.__start);
        const hitWidth = Math.max(6, baseXFor(point.__end) - hitX);

        return (
          <rect
            key={`${point.__key}-hit`}
            x={hitX}
            y={pad.top - 12}
            width={hitWidth}
            height={plotH + 24}
            fill="transparent"
            aria-label={`${point.label || "Metric window"} score ${formatScore(point.y)}`}
            cursor={isLockedElsewhere ? "default" : "pointer"}
            focusable="false"
            style={{ outline: "none" }}
            onMouseEnter={() => {
              if (!lockedKey) onHover(metricKey, point.__key);
            }}
            onMouseDown={(event) => {
              event.preventDefault();
            }}
            onClick={() => {
              if (!isLockedElsewhere) onToggleLock(metricKey, point.__key);
            }}
          />
        );
      })}
    </svg>
  );
}

function MetricLane({
  cursorTime,
  metric,
  maxX,
  hoveredKey,
  lockedKey,
  onClearCursor,
  onClearHover,
  onCursorMove,
  onHover,
  onToggleLock,
}) {
  const metricKey = metric.title;
  const data = normalizePoints(metric.points, maxX);
  const activeKey = lockedKey || hoveredKey;
  const activePoint = data.find((point) => point.__key === activeKey);
  const displayScore = activePoint ? activePoint.y : metric.score;
  const stateLabel = activePoint ? (lockedKey ? "locked region" : "hovered region") : "overall metric";

  return (
    <div
      className={`grid grid-cols-[minmax(148px,180px)_minmax(220px,1fr)_minmax(112px,136px)] items-center bg-paper/80 px-3 py-2 transition duration-150 ease-instrument hover:bg-[rgba(79,134,255,0.06)] max-md:grid-cols-[minmax(128px,150px)_1fr_98px] max-sm:grid-cols-1 ${
        lockedKey ? "bg-[rgba(31,94,255,0.075)]" : ""
      }`}
      onMouseLeave={() => {
        onClearCursor(metricKey);
        if (!lockedKey) onClearHover(metricKey);
      }}
    >
      <div className="min-w-0 border-r border-rule pr-3 max-sm:border-r-0 max-sm:pb-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 shrink-0" style={{ backgroundColor: lockedKey ? LOCK_STROKE : metric.color }} />
          <p className="truncate font-display text-lg font-bold text-ink">{metric.title}</p>
        </div>
        <p className="mt-1 font-mono text-[10px] text-muted">{metric.kind}</p>
      </div>

      <div className="relative min-w-0 px-3 max-sm:px-0">
        <LaneTrace
          activeKey={activeKey}
          color={metric.color}
          cursorTime={cursorTime}
          data={data}
          emptyLabel={metric.emptyLabel}
          lockedKey={lockedKey}
          maxX={maxX}
          metricKey={metricKey}
          onClearCursor={onClearCursor}
          onClearHover={onClearHover}
          onCursorMove={onCursorMove}
          onHover={onHover}
          onToggleLock={onToggleLock}
        />
      </div>

      <div className="min-w-0 border-l border-rule pl-3 text-right font-mono max-sm:border-l-0 max-sm:border-t max-sm:pt-2 max-sm:text-left">
        <p className={`truncate text-[10px] uppercase ${lockedKey ? "text-cobalt-deep" : activePoint ? "text-electric-blue" : "text-muted"}`}>
          {stateLabel}
        </p>
        <p className="mt-1 text-base font-bold text-ink">{formatScore(displayScore)}</p>
        <p className="mt-0.5 truncate text-[10px] text-muted">{activePoint?.label || "summary"}</p>
      </div>
    </div>
  );
}

export default function MetricLaneSuite({ metrics = [] }) {
  const [hoveredWindowByMetric, setHoveredWindowByMetric] = useState({});
  const [lockedWindowByMetric, setLockedWindowByMetric] = useState({});
  const [cursorTimeByMetric, setCursorTimeByMetric] = useState({});
  const maxX = Math.max(
    1,
    ...metrics.flatMap((metric) =>
      (metric.points || []).flatMap((point) => [
        Number(point.start) || 0,
        Number(point.x) || 0,
        Number(point.end) || 0,
      ]),
    ),
  );

  function handleHover(metricKey, windowKey) {
    setHoveredWindowByMetric((current) => ({
      ...current,
      [metricKey]: windowKey,
    }));
  }

  function handleClearHover(metricKey) {
    setHoveredWindowByMetric((current) => omitKey(current, metricKey));
  }

  function handleCursorMove(metricKey, cursorTime) {
    setCursorTimeByMetric((current) => ({
      ...current,
      [metricKey]: cursorTime,
    }));
  }

  function handleClearCursor(metricKey) {
    setCursorTimeByMetric((current) => omitKey(current, metricKey));
  }

  function handleToggleLock(metricKey, windowKey) {
    setLockedWindowByMetric((current) =>
      current[metricKey] === windowKey
        ? omitKey(current, metricKey)
        : {
            ...current,
            [metricKey]: windowKey,
          },
    );
    handleClearHover(metricKey);
  }

  return (
    <div className="overflow-hidden border-y border-rule-strong bg-paper">
      <div className="grid grid-cols-[minmax(148px,180px)_minmax(220px,1fr)_minmax(112px,136px)] border-b border-rule bg-porcelain/70 px-3 py-2 font-mono text-[10px] uppercase text-muted max-md:grid-cols-[minmax(128px,150px)_1fr_98px] max-sm:grid-cols-[1fr_72px]">
        <span className="min-w-0 truncate">Metric lane</span>
        <span className="signal-ruler min-w-0 max-sm:hidden">
          <span className="bg-porcelain/90 pr-2">Shared analysis clock</span>
        </span>
        <span className="min-w-0 truncate text-right">Score</span>
      </div>

      <div className="divide-y divide-rule">
        {metrics.map((metric) => (
          <MetricLane
            key={metric.title}
            cursorTime={cursorTimeByMetric[metric.title]}
            hoveredKey={hoveredWindowByMetric[metric.title]}
            lockedKey={lockedWindowByMetric[metric.title]}
            maxX={maxX}
            metric={metric}
            onClearCursor={handleClearCursor}
            onClearHover={handleClearHover}
            onCursorMove={handleCursorMove}
            onHover={handleHover}
            onToggleLock={handleToggleLock}
          />
        ))}
      </div>

      <div className="grid grid-cols-[minmax(148px,180px)_minmax(220px,1fr)_minmax(112px,136px)] border-t border-rule bg-porcelain/60 px-3 py-2 font-mono text-[10px] text-muted max-md:grid-cols-[minmax(128px,150px)_1fr_98px] max-sm:grid-cols-1">
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
