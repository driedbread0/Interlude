import { useEffect, useState } from "react";
import SpectrogramMatrix from "../visuals/SpectrogramMatrix";
import WaveformCanvas from "../visuals/WaveformCanvas";
import TransportBar from "./TransportBar";
import { formatDuration } from "../../lib/format";

export default function MainSignalDeck({ result }) {
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0.18);
  const duration = result?.project?.duration || 0;
  const currentTime = position * duration;
  const activeWindow =
    result?.windows?.tempo?.find((window) => currentTime >= window.start && currentTime <= window.end) ||
    result?.windows?.pitch?.find((window) => currentTime >= window.start && currentTime <= window.end) ||
    result?.windows?.dynamics?.find((window) => currentTime >= window.start && currentTime <= window.end);

  useEffect(() => {
    if (!playing) return undefined;

    const id = window.setInterval(() => {
      setPosition((current) => (current >= 0.985 ? 0.015 : current + 0.004));
    }, 72);

    return () => window.clearInterval(id);
  }, [playing]);

  return (
    <section className="workstation-region grid min-h-[590px] grid-rows-[auto_1fr_auto] overflow-hidden max-sm:min-h-[520px]">
      <div className="grid grid-cols-[minmax(0,1fr)_280px] border-b border-rule bg-paper/90 max-md:grid-cols-1">
        <div className="min-w-0 p-4">
          <p className="rule-label">Main playback analysis pane</p>
          <h2 className="display-title text-3xl max-sm:text-2xl">Signal assembly</h2>
        </div>
        <div className="min-w-0 border-l border-rule bg-porcelain/65 p-4 font-mono text-[11px] leading-5 text-muted max-md:border-l-0 max-md:border-t">
          <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-3 border-b border-rule pb-2">
            <span>active window</span>
            <span className="truncate text-right text-cobalt-deep">{activeWindow?.time_range || "not mapped"}</span>
          </div>
          <div className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-3">
            <span>playhead</span>
            <span className="truncate text-right text-ink">{formatDuration(currentTime)}</span>
          </div>
        </div>
      </div>

      <div className="grid min-h-0 grid-rows-[30px_minmax(170px,0.92fr)_minmax(230px,1.08fr)] bg-paper">
        <div className="signal-ruler grid grid-cols-5 border-b border-rule bg-porcelain/55 px-[58px] font-mono text-[10px] text-muted max-sm:px-10">
          {[0, 0.25, 0.5, 0.75, 1].map((tick, index) => (
            <span
              key={tick}
              className={`self-center ${tick === 1 ? "text-right" : tick === 0 ? "text-left" : "text-center"} ${index % 2 === 1 ? "max-sm:hidden" : ""}`}
            >
              {formatDuration(duration * tick)}
            </span>
          ))}
        </div>

        <div className="grid min-h-0 grid-cols-[58px_1fr] border-b border-rule">
          <div className="grid place-items-center border-r border-rule bg-porcelain/65 font-mono text-[10px] uppercase text-muted">
            amp
          </div>
          <div className="relative min-w-0 overflow-hidden bg-paper">
            <WaveformCanvas points={result?.visuals?.waveform} playhead={position} height={250} showPlayhead={false} />
            <div className="pointer-events-none absolute inset-y-0 border-l-2 border-cobalt-deep" style={{ left: `${position * 100}%` }} />
            <div className="pointer-events-none absolute left-3 top-3 max-w-[calc(100%-1.5rem)] truncate border border-rule bg-paper/95 px-2 py-1 font-mono text-[10px] text-muted">
              waveform envelope
            </div>
          </div>
        </div>

        <div className="grid min-h-0 grid-cols-[58px_1fr] bg-porcelain">
          <div className="grid place-items-center border-r border-rule bg-porcelain/70 font-mono text-[10px] uppercase text-muted">
            spec
          </div>
          <div className="relative min-w-0 overflow-hidden p-3 pb-10">
            <SpectrogramMatrix frameless rows={result?.visuals?.spectrogram?.rows} />
            <div className="pointer-events-none absolute inset-x-3 top-3 h-px bg-porcelain/80" />
            <div className="pointer-events-none absolute inset-3">
              <div className="absolute inset-y-0 border-l-2 border-cobalt-deep" style={{ left: `${position * 100}%` }} />
              <div className="absolute left-2 top-2 max-w-[calc(100%-1rem)] truncate border border-cobalt bg-paper/95 px-2 py-1 font-mono text-[10px] text-cobalt-deep">
                {activeWindow?.time_range || "active region"}
              </div>
            </div>
          <input
            aria-label="Scrub through song"
            className="absolute inset-x-4 bottom-4 z-10 h-5 cursor-pointer accent-cobalt opacity-85 sm:inset-x-6"
            max="1"
            min="0"
            step="0.001"
            type="range"
            value={position}
            onChange={(event) => setPosition(Number(event.target.value))}
          />
          <div className="pointer-events-none absolute inset-x-4 bottom-[27px] h-px bg-rule-strong sm:inset-x-6" />
          </div>
        </div>
      </div>

      <TransportBar
        duration={duration}
        playing={playing}
        position={position}
        setPlaying={setPlaying}
      />
    </section>
  );
}
