import { Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { formatDuration } from "../../lib/format";

export default function TransportBar({ playing, setPlaying, position, duration }) {
  return (
    <div className="grid grid-cols-[auto_minmax(90px,1fr)_auto] items-center gap-4 border-t border-rule-strong bg-paper px-4 py-3 max-sm:grid-cols-[auto_1fr]">
      <div className="flex items-center gap-2">
        <button className="grid h-9 w-9 place-items-center border border-rule bg-porcelain text-muted transition duration-150 ease-instrument hover:border-cobalt hover:text-cobalt" type="button">
          <SkipBack className="h-4 w-4" />
        </button>
        <button
          className="grid h-11 w-11 place-items-center border border-cobalt-deep bg-cobalt text-porcelain transition duration-150 ease-instrument hover:bg-cobalt-deep"
          type="button"
          onClick={() => setPlaying((current) => !current)}
        >
          {playing ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        </button>
        <button className="grid h-9 w-9 place-items-center border border-rule bg-porcelain text-muted transition duration-150 ease-instrument hover:border-cobalt hover:text-cobalt" type="button">
          <SkipForward className="h-4 w-4" />
        </button>
      </div>

      <div className="fine-ruler h-6 min-w-0 border-y border-rule bg-porcelain/70" />

      <p className="whitespace-nowrap text-right font-mono text-xs text-muted max-sm:col-span-2 max-sm:text-left">
        {formatDuration(position * duration)} / {formatDuration(duration)}
      </p>
    </div>
  );
}
