import AnalysisNoteInput from "./AnalysisNoteInput";
import BrandMasthead from "./BrandMasthead";
import ResumeProjects from "./ResumeProjects";
import RootModeControl from "./RootModeControl";
import UploadInstrument from "./UploadInstrument";

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
  const vocalCapability = options?.capabilities?.vocal_separation;
  const vocalSeparationAvailable = Boolean(vocalCapability?.available);

  return (
    <main className="min-h-screen overflow-hidden bg-canvas text-ink">
      <div className="mx-auto grid min-h-screen max-w-[1540px] grid-rows-[auto_1fr] px-6 py-5">
        <BrandMasthead onOpenProjects={onOpenProjects} />

        <section className="grid min-h-0 grid-cols-[minmax(0,1fr)_410px] gap-5 py-5 max-xl:grid-cols-1">
          <UploadInstrument
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            onAnalyze={onAnalyze}
            status={status}
          />

          <aside className="grid content-start gap-4">
            <div className="workstation-region angled-cut overflow-hidden">
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
