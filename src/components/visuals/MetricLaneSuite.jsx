import { AlertTriangle, LockKeyhole } from "lucide-react";
import { formatScore } from "../../lib/format";

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

function normalizePoints(points, duration) {
  return (points || [])
    .map((point, index) => {
      const fallbackX = Number(point?.x) || 0;
      const start = clamp(Number(point?.start) || fallbackX, 0, duration);
      const requestedEnd = Number(point?.end) || start;
      const end = clamp(Math.max(start + duration * 0.003, requestedEnd), 0, duration);

      return {
        ...point,
        y: point?.ambiguous ? 0.5 : clamp(point?.y),
        __key: `${start.toFixed(3)}-${end.toFixed(3)}-${index}`,
        __start: start,
        __end: end,
        __mid: (start + end) / 2,
      };
    })
    .sort((a, b) => a.__start - b.__start);
}

function pointAtTime(points, time) {
  return points.find((point) => time >= point.__start && time <= point.__end) || null;
}

function coordinates(points, duration) {
  const width = 1000;
  return points.map((point) => ({
    ...point,
    __x: (point.__mid / Math.max(1, duration)) * width,
    __y: 76 - point.y * 58,
  }));
}

function pointGroups(points) {
  const groups = [];
  let group = [];

  points.forEach((point) => {
    if (point.ambiguous) {
      if (group.length) groups.push(group);
      group = [];
      return;
    }
    group.push(point);
  });
  if (group.length) groups.push(group);
  return groups;
}

function pathForGroup(group, kind) {
  if (!group.length) return "";
  let path = `M ${group[0].__x.toFixed(2)} ${group[0].__y.toFixed(2)}`;

  for (let index = 1; index < group.length; index += 1) {
    const previous = group[index - 1];
    const point = group[index];

    if (kind === "pitch" || kind === "dynamics") {
      const midpoint = (previous.__x + point.__x) / 2;
      path += ` C ${midpoint.toFixed(2)} ${previous.__y.toFixed(2)}, ${midpoint.toFixed(2)} ${point.__y.toFixed(2)}, ${point.__x.toFixed(2)} ${point.__y.toFixed(2)}`;
    } else {
      path += ` L ${point.__x.toFixed(2)} ${point.__y.toFixed(2)}`;
    }
  }
  return path;
}

function tracePaths(points, duration, kind) {
  return pointGroups(coordinates(points, duration)).map((group) => ({
    key: group.map((point) => point.__key).join("|"),
    path: pathForGroup(group, kind),
    area: kind === "dynamics"
      ? `${pathForGroup(group, kind)} L ${group[group.length - 1].__x.toFixed(2)} 82 L ${group[0].__x.toFixed(2)} 82 Z`
      : null,
  }));
}

function confidenceFor(point) {
  for (const key of ["confidence", "correlation", "voiced_probability", "mean_probability"]) {
    const value = Number(point?.[key]);
    if (Number.isFinite(value)) return clamp(value, 0.25, 1);
  }
  return 1;
}

function MetricLane({ metric, transport }) {
  const { duration, evidenceTime, focusMetric, focusState, inspectTime, inspectionTime, selectEvidence, selectedEvidence } = transport;
  const points = normalizePoints(metric.points, duration);
  const activePoint = pointAtTime(points, evidenceTime);
  const selected = selectedEvidence?.metric === metric.key;
  const focused = focusMetric === metric.key;
  const displayScore = activePoint?.ambiguous ? null : activePoint?.y ?? metric.score;
  const paths = tracePaths(points, duration, metric.key);
  const activeStart = activePoint ? (activePoint.__start / Math.max(1, duration)) * 100 : 0;
  const activeWidth = activePoint ? Math.max(0.5, ((activePoint.__end - activePoint.__start) / Math.max(1, duration)) * 100) : 0;
  const inspecting = inspectionTime !== null && inspectionTime !== undefined;
  const activeConfidence = confidenceFor(activePoint);

  function eventTime(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return clamp((event.clientX - bounds.left) / Math.max(1, bounds.width)) * duration;
  }

  function handleSelect(event) {
    const time = eventTime(event);
    const point = pointAtTime(points, time);
    if (!point) return;

    selectEvidence({
      ...point,
      metric: metric.key,
      metricTitle: metric.title,
      color: metric.color,
      start: point.__start,
      end: point.__end,
    }, true);
  }

  return (
    <article
      className={`metric-channel focus-reactive ${selected ? "is-selected" : ""} ${focused ? `is-focused is-${focusState}` : ""}`}
      data-evidence-metric={metric.key}
      data-focus-stage="metric"
      data-graph-kind={metric.key}
      style={{ "--metric-color": metric.color }}
    >
      <div className="metric-channel-label">
        <div className="flex items-center gap-2">
          <span className="metric-channel-led" />
          <h3>{metric.title}</h3>
        </div>
        <p>{metric.kind}</p>
      </div>

      <div
        className="metric-channel-plot"
        onPointerMove={(event) => inspectTime(eventTime(event), metric.key)}
        onPointerLeave={() => inspectTime(null)}
        onMouseLeave={() => inspectTime(null)}
        onClick={handleSelect}
      >
        <svg viewBox="0 0 1000 88" preserveAspectRatio="none" aria-label={`${metric.title} timeline`}>
          {[0.25, 0.5, 0.75].map((value) => (
            <line key={value} x1="0" x2="1000" y1={76 - value * 58} y2={76 - value * 58} className="metric-grid-line" />
          ))}
          {Array.from({ length: 17 }).map((_, index) => (
            <line key={index} x1={(index / 16) * 1000} x2={(index / 16) * 1000} y1="8" y2="82" className={index % 4 === 0 ? "metric-time-line major" : "metric-time-line"} />
          ))}
          {metric.key === "tempo" && points.filter((point) => !point.ambiguous).map((point) => (
            <line
              key={`beat-${point.__key}`}
              x1={(point.__mid / Math.max(1, duration)) * 1000}
              x2={(point.__mid / Math.max(1, duration)) * 1000}
              y1="67"
              y2="82"
              className="metric-tempo-reference"
            />
          ))}
          {points.filter((point) => point.ambiguous).map((point) => (
            <rect
              key={point.__key}
              x={(point.__start / Math.max(1, duration)) * 1000}
              y="8"
              width={Math.max(3, ((point.__end - point.__start) / Math.max(1, duration)) * 1000)}
              height="74"
              className="metric-ambiguous-region"
            />
          ))}
          {paths.map((segment) => segment.area && (
            <path key={`area-${segment.key}`} d={segment.area} className="metric-dynamics-area" vectorEffect="non-scaling-stroke" />
          ))}
          {paths.map((segment) => (
            <g key={segment.key}>
              <path d={segment.path} className="metric-trace-underlay" vectorEffect="non-scaling-stroke" />
              <path d={segment.path} className="metric-trace-path" vectorEffect="non-scaling-stroke" />
            </g>
          ))}
          {activePoint && !activePoint.ambiguous && (
            <circle
              cx={(activePoint.__mid / Math.max(1, duration)) * 1000}
              cy={76 - activePoint.y * 58}
              r="4.5"
              className="metric-active-node"
              opacity={activeConfidence}
              vectorEffect="non-scaling-stroke"
            >
              <title>{activePoint.tooltip || `${activePoint.label || metric.title}: ${formatScore(activePoint.y)}`}</title>
            </circle>
          )}
        </svg>

        {activePoint && (
          <div
            className={`metric-active-window ${activePoint.ambiguous ? "is-ambiguous" : ""}`}
            style={{ left: `${activeStart}%`, width: `${activeWidth}%` }}
          />
        )}
        <div
          className={`analysis-live-cursor metric-cursor ${inspecting ? "is-inspecting" : ""}`}
          style={inspecting ? { left: `${clamp(inspectionTime / Math.max(1, duration)) * 100}%` } : undefined}
          aria-hidden="true"
        />
      </div>

      <div className="metric-channel-readout">
        <p>{activePoint ? "at cursor" : "overall"}</p>
        <strong>{formatScore(displayScore)}</strong>
        <span className={activePoint?.ambiguous ? "text-warning" : ""}>
          {activePoint?.ambiguous ? (
            <><AlertTriangle className="h-3 w-3" /> low confidence</>
          ) : selected ? (
            <><LockKeyhole className="h-3 w-3" /> evidence locked</>
          ) : activePoint?.evidence_label || activePoint?.label || "global score"}
        </span>
      </div>
    </article>
  );
}

export default function MetricLaneSuite({ metrics = [], transport }) {
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="metric-console">
      <div className="metric-console-head">
        <span>analysis channel</span>
        <div className="metric-console-ruler"><span>shared source clock</span></div>
        <span className="text-right">normalized evidence</span>
      </div>

      <div className="divide-y divide-rule">
        {metrics.map((metric) => <MetricLane key={metric.key} metric={metric} transport={transport} />)}
      </div>

      <div className="metric-console-foot">
        <span>linked window inspection</span>
        <div className="grid grid-cols-5">
          {ticks.map((tick, index) => (
            <span key={tick} className={index === 4 ? "text-right" : index === 0 ? "text-left" : "text-center"}>
              {Math.round(transport.duration * tick)}s
            </span>
          ))}
        </div>
        <span className="text-right">click to lock</span>
      </div>
    </div>
  );
}
