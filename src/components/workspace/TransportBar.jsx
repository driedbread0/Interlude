import { Pause, Play, RotateCcw, RotateCw, Volume2 } from "lucide-react";
import { useRef } from "react";
import { formatDuration } from "../../lib/format";
import { gsap, useGSAP } from "../../lib/motion";

export default function TransportBar({ transport }) {
  const { currentTime, duration, playing, position, seek, skip, togglePlayback } = transport;
  const buttonRef = useRef(null);

  useGSAP(() => {
    if (!buttonRef.current) return;
    gsap.to(buttonRef.current, {
      scale: playing ? 1.045 : 1,
      boxShadow: playing ? "0 0 0 5px rgba(31, 94, 255, 0.15)" : "0 0 0 0 rgba(31, 94, 255, 0)",
      duration: 0.26,
      ease: "power2.out",
    });
  }, { dependencies: [playing] });

  return (
    <div className="transport-rail grid grid-cols-[auto_minmax(160px,1fr)_auto] items-center gap-5 border-t border-rule-strong bg-paper px-5 py-3 max-sm:grid-cols-[auto_1fr] max-sm:gap-3">
      <div className="flex items-center gap-1.5">
        <button className="transport-skip" aria-label="Rewind ten seconds" type="button" onClick={() => skip(-10)}>
          <RotateCcw className="h-4 w-4" /><span>10</span>
        </button>
        <button ref={buttonRef} className="transport-play" aria-label={playing ? "Pause" : "Play"} type="button" onClick={togglePlayback}>
          {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 translate-x-px" />}
        </button>
        <button className="transport-skip" aria-label="Forward ten seconds" type="button" onClick={() => skip(10)}>
          <RotateCw className="h-4 w-4" /><span>10</span>
        </button>
      </div>

      <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3">
        <span className="font-mono text-[10px] text-cobalt-deep">{formatDuration(currentTime)}</span>
        <div className="transport-scrub relative">
          <div className="transport-scrub-fill" style={{ width: `${position * 100}%` }} />
          <input
            aria-label="Scrub through song"
            max="1"
            min="0"
            step="0.001"
            type="range"
            value={position}
            onChange={(event) => seek(Number(event.target.value))}
          />
        </div>
        <span className="font-mono text-[10px] text-muted">{formatDuration(duration)}</span>
      </div>

      <div className="flex items-center gap-2 font-mono text-[9px] uppercase text-muted max-sm:hidden">
        <Volume2 className="h-3.5 w-3.5" /> monitor
        <span className={`h-1.5 w-1.5 rounded-full ${playing ? "bg-teal" : "bg-rule-strong"}`} />
      </div>
    </div>
  );
}
