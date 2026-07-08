import { ArrowRight, FileAudio2, Upload } from "lucide-react";
import WaveformCanvas from "../visuals/WaveformCanvas";

export default function UploadInstrument({ selectedFile, setSelectedFile, onAnalyze, status }) {
  const analyzing = status === "analyzing";

  return (
    <section className="signal-surface grid min-h-[560px] grid-rows-[auto_1fr_auto] overflow-hidden">
      <div className="grid grid-cols-[1fr_180px] border-b border-rule max-md:grid-cols-1">
        <div className="p-6">
          <p className="rule-label mb-3">Analysis intake deck</p>
          <h2 className="display-title max-w-4xl text-5xl leading-[0.94] max-lg:text-4xl">
            Start a project. Prepare the diagnostic surface.
          </h2>
        </div>
        <div className="border-l border-rule bg-[rgba(31,94,255,0.08)] p-5 max-md:border-l-0 max-md:border-t">
          <p className="font-mono text-[10px] font-bold uppercase text-cobalt-deep">Auto map</p>
          <p className="mt-4 text-sm leading-6 text-ink-soft">
            Timing, pitch, harmonic motion, waveform, spectrum, and project feedback.
          </p>
        </div>
      </div>

      <label className="group relative m-5 cursor-pointer overflow-hidden border border-dashed border-rule-strong bg-porcelain transition duration-150 ease-instrument hover:border-cobalt hover:bg-[rgba(79,134,255,0.08)]">
        <input
          className="sr-only"
          type="file"
          accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg,.aiff,.aif"
          onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
        />
        <div className="absolute inset-x-0 top-10 h-48 opacity-80">
          <WaveformCanvas quiet height={190} />
        </div>
        <div className="grid min-h-[390px] place-items-center p-8">
          <div className="relative z-10 max-w-xl text-center">
            <div className="mx-auto mb-5 grid h-16 w-16 place-items-center border border-cobalt bg-paper text-cobalt shadow-insetline transition duration-150 ease-instrument group-hover:-translate-y-1">
              {selectedFile ? <FileAudio2 className="h-7 w-7" /> : <Upload className="h-7 w-7" />}
            </div>
            <p className="font-display text-3xl font-bold text-ink">
              {selectedFile ? selectedFile.name : "Choose or drag an audio file"}
            </p>
            <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-ink-soft">
              The file becomes a reusable project with signal views, metric windows, and written diagnostic feedback.
            </p>
          </div>
        </div>
      </label>

      <div className="grid grid-cols-[1fr_auto] items-stretch gap-3 border-t border-rule p-4 max-sm:grid-cols-1">
        <div className="grid grid-cols-3 border border-rule bg-paper text-center font-mono text-[10px] uppercase text-muted max-md:hidden">
          <div className="border-r border-rule p-3">Waveform</div>
          <div className="border-r border-rule p-3">Spectrogram</div>
          <div className="p-3">Metric windows</div>
        </div>
        <button
          className="blue-button flex items-center justify-center gap-3 px-8"
          disabled={!selectedFile || analyzing}
          type="button"
          onClick={onAnalyze}
        >
          {analyzing ? "Analyzing" : "Analyze track"}
          <ArrowRight className={`h-5 w-5 ${analyzing ? "animate-pulse" : ""}`} />
        </button>
      </div>
    </section>
  );
}
