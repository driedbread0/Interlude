import { ArrowRight, FileAudio2, ScanLine, Upload } from "lucide-react";
import { useRef, useState } from "react";
import WaveformCanvas from "../visuals/WaveformCanvas";
import { gsap, useGSAP } from "../../lib/motion";

function fileSize(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadInstrument({ selectedFile, setSelectedFile, onAnalyze, status }) {
  const analyzing = status === "analyzing";
  const [dragging, setDragging] = useState(false);
  const instrumentRef = useRef(null);
  const scannerRef = useRef(null);

  useGSAP(() => {
    if (!scannerRef.current) return;

    if (analyzing) {
      gsap.set(scannerRef.current, { xPercent: -100, opacity: 1 });
      gsap.to(scannerRef.current, { xPercent: 100, duration: 1.5, repeat: -1, ease: "none" });
    } else {
      gsap.killTweensOf(scannerRef.current);
      gsap.to(scannerRef.current, { opacity: 0, duration: 0.2 });
    }
  }, { dependencies: [analyzing], scope: instrumentRef });

  useGSAP(() => {
    if (!selectedFile) return;
    gsap.fromTo("[data-file-readout]", { y: 8, opacity: 0 }, { y: 0, opacity: 1, duration: 0.36, ease: "power3.out" });
    gsap.fromTo("[data-intake-wave]", { opacity: 0.28, scaleY: 0.7 }, { opacity: 1, scaleY: 1, duration: 0.58, ease: "power2.out" });
  }, { dependencies: [selectedFile?.name], scope: instrumentRef });

  function acceptFiles(files) {
    const file = files?.[0];
    if (file) setSelectedFile(file);
  }

  return (
    <section ref={instrumentRef} data-upload-instrument className="intake-signal-deck grid min-h-[650px] grid-rows-[auto_1fr_auto] overflow-hidden">
      <div className="grid grid-cols-[minmax(0,1fr)_210px] border-b border-rule-strong max-md:grid-cols-1">
        <div className="px-6 py-7 max-sm:px-4">
          <div className="mb-3 flex items-center gap-2"><ScanLine className="h-3.5 w-3.5 text-cobalt" /><p className="rule-label">Source intake / channel 01</p></div>
          <h2 className="display-title max-w-4xl text-[clamp(2.5rem,5vw,5.2rem)] leading-[0.86]">
            Inspect what the music is doing.
          </h2>
          <p className="mt-5 max-w-2xl text-sm leading-6 text-ink-soft">
            Load a recording to map its timing, pitch, tonal center, harmonic motion, density, and dynamics onto one synchronized diagnostic surface.
          </p>
        </div>
        <div className="intake-spec-list border-l border-rule bg-porcelain/60 max-md:border-l-0 max-md:border-t">
          <div><span>engine</span><strong>full-track analysis</strong></div>
          <div><span>key map</span><strong>KS correlation</strong></div>
          <div><span>output</span><strong>windowed evidence</strong></div>
        </div>
      </div>

      <label
        className={`intake-drop-zone group ${dragging ? "is-dragging" : ""} ${selectedFile ? "has-file" : ""}`}
        onDragEnter={() => setDragging(true)}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); acceptFiles(event.dataTransfer.files); }}
      >
        <input
          className="sr-only"
          type="file"
          accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg,.aiff,.aif"
          onChange={(event) => acceptFiles(event.target.files)}
        />
        <div data-intake-wave className="absolute inset-x-0 top-1/2 h-[240px] -translate-y-1/2 opacity-70">
          <WaveformCanvas quiet={!selectedFile} height={220} showGrid={false} tone="dark" />
        </div>
        <div className="intake-scan-grid" />
        <div ref={scannerRef} className="intake-scanner" />
        <div data-file-readout className="relative z-10 mx-auto max-w-xl text-center">
          <div className="intake-source-icon">
            {selectedFile ? <FileAudio2 className="h-7 w-7" /> : <Upload className="h-7 w-7" />}
          </div>
          <p className="font-display text-3xl font-bold text-ink max-sm:text-2xl">
            {selectedFile ? selectedFile.name : "Choose or drag an audio source"}
          </p>
          <p className="mx-auto mt-2 max-w-md font-mono text-[9px] uppercase tracking-[0.08em] text-signal-muted">
            {selectedFile ? `${selectedFile.type || "audio"} · ${fileSize(selectedFile.size)} · armed` : "WAV · MP3 · M4A · FLAC · OGG · AIFF"}
          </p>
        </div>
      </label>

      <div className="intake-command-rail grid grid-cols-[1fr_auto] items-stretch border-t border-rule-strong max-sm:grid-cols-1">
        <div className="grid grid-cols-4 divide-x divide-rule bg-porcelain/70 text-center font-mono text-[8px] uppercase tracking-[0.08em] text-muted max-md:hidden">
          <div>01 / decode</div><div>02 / map</div><div>03 / correlate</div><div>04 / interpret</div>
        </div>
        <button className="intake-analyze-button" disabled={!selectedFile || analyzing} type="button" onClick={onAnalyze}>
          <span>{analyzing ? "Analysis running" : "Run diagnostic"}</span>
          <ArrowRight className="h-5 w-5" />
        </button>
      </div>
    </section>
  );
}
