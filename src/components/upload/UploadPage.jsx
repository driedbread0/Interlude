import { useRef } from "react";
import AnalysisNoteInput from "./AnalysisNoteInput";
import BrandMasthead from "./BrandMasthead";
import ResumeProjects from "./ResumeProjects";
import RootModeControl from "./RootModeControl";
import UploadInstrument from "./UploadInstrument";
import { gsap, useGSAP } from "../../lib/motion";

export default function UploadPage({
  options,
  selectedFile,
  setSelectedFile,
  extraPrompt,
  setExtraPrompt,
  autoKey,
  setAutoKey,
  root,
  setRoot,
  scaleType,
  setScaleType,
  separateVocals,
  setSeparateVocals,
  onAnalyze,
  status,
  projects,
  onOpenProjects,
  onSelectProject,
}) {
  const intakeRef = useRef(null);
  const vocalCapability = options?.capabilities?.vocal_separation;
  const vocalSeparationAvailable = Boolean(vocalCapability?.available);

  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const timeline = gsap.timeline({ defaults: { ease: "power3.out" } });
      timeline
        .from("[data-intake-masthead]", { y: -14, opacity: 0, duration: 0.4 })
        .from("[data-upload-instrument]", { y: 20, opacity: 0, duration: 0.58 }, "-=0.18")
        .from("[data-intake-controls]", { x: 20, opacity: 0, duration: 0.5 }, "-=0.38");
    });
    return () => media.revert();
  }, { scope: intakeRef });

  return (
    <main ref={intakeRef} className="interlude-page-field min-h-screen bg-canvas text-ink">
      <div className="mx-auto grid min-h-screen max-w-[1640px] grid-rows-[auto_1fr] px-5 py-4 max-sm:px-0 max-sm:py-0">
        <BrandMasthead onOpenProjects={onOpenProjects} />

        <section className="intake-instrument grid min-h-0 grid-cols-[minmax(0,1fr)_390px] overflow-hidden bg-paper shadow-panel max-xl:grid-cols-1">
          <UploadInstrument
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            onAnalyze={onAnalyze}
            status={status}
          />

          <aside data-intake-controls className="intake-configuration-rail border-l border-rule-strong bg-paper max-xl:border-l-0 max-xl:border-t">
            <div className="overflow-hidden">
              <RootModeControl
                options={options}
                autoKey={autoKey}
                setAutoKey={setAutoKey}
                root={root}
                setRoot={setRoot}
                scaleType={scaleType}
                setScaleType={setScaleType}
              />
              <section className="border-t border-rule px-4 py-3">
                <label
                  className={`flex items-start gap-3 ${
                    vocalSeparationAvailable ? "cursor-pointer" : "cursor-not-allowed opacity-60"
                  }`}
                >
                  <input
                    className="mt-0.5 h-4 w-4 accent-cobalt"
                    type="checkbox"
                    checked={separateVocals}
                    onChange={(event) => setSeparateVocals(event.target.checked)}
                    disabled={!vocalSeparationAvailable || status === "analyzing"}
                  />
                  <span>
                    <span className="rule-label block text-ink">Isolate vocals for pitch tracking</span>
                    <span className="mt-1 block text-xs leading-5 text-muted">
                      {vocalSeparationAvailable
                        ? `Uses ${vocalCapability.model || "Demucs"}; analysis will take longer.`
                        : "Optional setup required: install requirements-vocal.txt and restart."}
                    </span>
                  </span>
                </label>
              </section>
              <AnalysisNoteInput value={extraPrompt} onChange={setExtraPrompt} />
              <section className="border-t border-rule bg-[rgba(31,94,255,0.06)] p-4">
                <div className="mb-3 flex items-center justify-between">
                  <p className="rule-label text-cobalt-deep">Analysis path</p>
                  <span className="font-mono text-[10px] uppercase text-muted">armed sequence</span>
                </div>
                <ol className="grid gap-2 text-sm leading-6 text-ink-soft">
                  <li className="grid grid-cols-[34px_1fr] border-t border-rule pt-2">
                    <span className="font-mono text-cobalt">01</span>
                    <span>Extract timing, pitch, harmony, and dynamics windows.</span>
                  </li>
                  <li className="grid grid-cols-[34px_1fr] border-t border-rule pt-2">
                    <span className="font-mono text-cobalt">02</span>
                    <span>Render waveform, spectrum, chroma, and metric lanes.</span>
                  </li>
                  <li className="grid grid-cols-[34px_1fr] border-t border-rule pt-2">
                    <span className="font-mono text-cobalt">03</span>
                    <span>Attach audio and generate written diagnostics.</span>
                  </li>
                </ol>
              </section>
            </div>
            <ResumeProjects projects={projects} onOpenProjects={onOpenProjects} onSelectProject={onSelectProject} />
          </aside>
        </section>
      </div>
    </main>
  );
}
