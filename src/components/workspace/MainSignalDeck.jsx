import { Crosshair, ScanLine } from "lucide-react";
import SpectrogramMatrix from "../visuals/SpectrogramMatrix";
import WaveformCanvas from "../visuals/WaveformCanvas";
import TransportBar from "./TransportBar";
import { formatDuration, formatScore } from "../../lib/format";

function clamp(value, min = 0, max = 1) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

function EvidenceRegion({ evidence, duration, selected = false }) {
  if (!evidence || !duration) return null;

  const start = clamp((Number(evidence.start) || 0) / duration);
  const end = clamp((Number(evidence.end) || Number(evidence.start) || 0) / duration);

  return (
    <div
      className={`evidence-region focus-reactive ${selected ? "is-selected" : ""}`}
      data-evidence-metric={evidence.metric || "harmony"}
      style={{ left: `${start * 100}%`, width: `${Math.max(0.5, (end - start) * 100)}%` }}
    />
  );
}

function LiveCursor({ inspectionTime, duration }) {
  const inspecting = inspectionTime !== null && inspectionTime !== undefined;
  const inspectionProgress = duration ? clamp(inspectionTime / duration) : 0;

  return (
    <div
      className={`analysis-live-cursor ${inspecting ? "is-inspecting" : ""}`}
      style={inspecting ? { left: `${inspectionProgress * 100}%` } : undefined}
      aria-hidden="true"
    >
      <span className="analysis-cursor-cap" />
    </div>
  );
}

export default function MainSignalDeck({ result, transport }) {
  const {
    activeWindows,
    audioAvailable,
    audioStatus,
    currentTime,
    duration,
    evidenceTime,
    inspectTime,
    inspectionTime,
    selectedEvidence,
    seek,
  } = transport;
  const primaryWindow = selectedEvidence || activeWindows.harmony || activeWindows.tempo;
  const inspecting = inspectionTime !== null && inspectionTime !== undefined;
  const ticks = [0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1];

  function timeFromEvent(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return clamp((event.clientX - bounds.left) / Math.max(1, bounds.width)) * duration;
  }

  return (
    <section data-signal-deck data-focus-stage="signal" className="signal-deck focus-reactive overflow-hidden bg-paper">
      <header className="signal-deck-header grid grid-cols-[minmax(0,1fr)_auto] items-end gap-6 px-5 py-4 max-md:grid-cols-1 max-md:gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ScanLine className="h-3.5 w-3.5 text-cobalt" />
            <p className="rule-label">Primary signal deck / synchronized source view</p>
          </div>
          <h2 className="display-title mt-2 text-[clamp(3.25rem,5.4vw,5.75rem)] leading-[0.86]">Signal inspection</h2>
        </div>
        <div className="grid min-w-[310px] grid-cols-3 divide-x divide-rule border-y border-rule py-2 font-mono text-[10px] uppercase text-muted max-md:min-w-0">
          <div className="px-3 first:pl-0">
            <span className="block">cursor</span>
            <strong className="mt-1 block text-sm text-ink">{formatDuration(evidenceTime)}</strong>
          </div>
          <div className="px-3">
            <span className="block">window</span>
            <strong className="mt-1 block truncate text-sm text-cobalt-deep">
              {primaryWindow?.time_range || "live"}
            </strong>
          </div>
          <div className="px-3">
            <span className="block">source</span>
            <strong className="mt-1 block text-sm text-teal-deep">{audioAvailable ? "audio" : audioStatus}</strong>
          </div>
        </div>
      </header>

      <div className="control-readout-strip grid grid-cols-4 divide-x divide-rule max-md:grid-cols-2 max-md:divide-y">
        <div><span>global tempo</span><strong>{Number(result?.project?.bpm || 0).toFixed(2)} BPM</strong></div>
        <div><span>tempo interval</span><strong>{formatScore(activeWindows.tempo?.score)}</strong></div>
        <div><span>harmonic evidence</span><strong className={activeWindows.harmony?.ambiguous ? "text-warning" : "text-violet"}>{activeWindows.harmony?.ambiguous ? "LOW CONF." : formatScore(activeWindows.harmony?.score)}</strong></div>
        <div><span>pitch reliability</span><strong className="text-teal-deep">{result?.pitch_tracking?.reliability || "unknown"}</strong></div>
      </div>

      <TransportBar transport={transport} />

      <div className="signal-chassis">
        <div className="grid grid-cols-[64px_minmax(0,1fr)] border-b border-signal-rule bg-signal-ink">
          <div className="grid place-items-center border-r border-signal-rule font-mono text-[9px] uppercase tracking-[0.16em] text-signal-muted">
            time
          </div>
          <div className="signal-time-ruler grid h-8 items-end pb-1.5 font-mono text-[9px] text-signal-muted" style={{ gridTemplateColumns: `repeat(${ticks.length}, 1fr)` }}>
            {ticks.map((tick, index) => (
              <span key={tick} className={index === ticks.length - 1 ? "text-right" : index === 0 ? "text-left" : "text-center max-sm:odd:hidden"}>
                {formatDuration(duration * tick)}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-[64px_minmax(0,1fr)] border-b border-signal-rule bg-signal-ink">
          <div className="signal-axis border-r border-signal-rule">
            <span>+1</span><span>AMP</span><span>−1</span>
          </div>
          <div
            className="signal-interaction relative h-[210px] min-w-0 cursor-crosshair overflow-hidden max-sm:h-[170px]"
            onPointerMove={(event) => inspectTime(timeFromEvent(event))}
            onPointerLeave={() => inspectTime(null)}
            onMouseLeave={() => inspectTime(null)}
            onClick={(event) => seek(timeFromEvent(event) / Math.max(1, duration))}
          >
            <WaveformCanvas points={result?.visuals?.waveform} height={240} showPlayhead={false} tone="dark" />
            <EvidenceRegion evidence={primaryWindow} duration={duration} selected={Boolean(selectedEvidence)} />
            <LiveCursor inspectionTime={inspectionTime} duration={duration} />
            <div className="signal-surface-label"><Crosshair className="h-3 w-3" /> waveform / RMS envelope</div>
          </div>
        </div>

        <div className="grid grid-cols-[64px_minmax(0,1fr)] bg-signal-ink">
          <div className="signal-axis border-r border-signal-rule">
            <span>HI</span><span>HZ</span><span>LO</span>
          </div>
          <div
            className="signal-interaction relative h-[265px] min-w-0 cursor-crosshair overflow-hidden max-sm:h-[220px]"
            onPointerMove={(event) => inspectTime(timeFromEvent(event))}
            onPointerLeave={() => inspectTime(null)}
            onMouseLeave={() => inspectTime(null)}
            onClick={(event) => seek(timeFromEvent(event) / Math.max(1, duration))}
          >
            <SpectrogramMatrix frameless rows={result?.visuals?.spectrogram?.rows} tone="dark" />
            <EvidenceRegion evidence={primaryWindow} duration={duration} selected={Boolean(selectedEvidence)} />
            <LiveCursor inspectionTime={inspectionTime} duration={duration} />
            <div className="signal-surface-label"><ScanLine className="h-3 w-3" /> spectral energy</div>
            {inspecting && (
              <div className="signal-hover-readout" style={{ left: `${clamp(inspectionTime / Math.max(1, duration)) * 100}%` }}>
                <span>{formatDuration(evidenceTime)}</span>
                <strong>{activeWindows.harmony?.ambiguous ? "AMBIGUOUS HARMONY" : activeWindows.harmony?.local_key_label || "SIGNAL REGION"}</strong>
              </div>
            )}
          </div>
        </div>
      </div>

    </section>
  );
}
