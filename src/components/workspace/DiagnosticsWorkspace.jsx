import AnalysisBand from "./AnalysisBand";
import DiagnosticRail from "./DiagnosticRail";
import MainSignalDeck from "./MainSignalDeck";
import WorkspaceHeader from "./WorkspaceHeader";

export default function DiagnosticsWorkspace({ result, onNewAnalysis, onOpenProjects }) {
  return (
    <main className="min-h-screen bg-canvas p-4 text-ink max-sm:p-2">
      <div className="mx-auto grid h-[calc(100vh-2rem)] max-w-[1600px] grid-rows-[auto_1fr] overflow-hidden border border-rule-strong bg-paper shadow-panel max-xl:h-auto max-xl:min-h-[calc(100vh-2rem)] max-xl:overflow-visible max-sm:min-h-[calc(100vh-1rem)]">
        <WorkspaceHeader result={result} onNewAnalysis={onNewAnalysis} onOpenProjects={onOpenProjects} />

        <section className="grid min-h-0 grid-cols-[minmax(0,1fr)_420px] gap-4 overflow-hidden p-4 max-xl:grid-cols-1 max-xl:overflow-visible max-md:p-3 max-sm:p-2">
          <div className="grid min-h-0 grid-rows-[minmax(520px,1fr)_auto] gap-4 overflow-auto pr-1 max-xl:overflow-visible max-xl:pr-0">
            <MainSignalDeck result={result} />
            <AnalysisBand result={result} />
          </div>

          <DiagnosticRail result={result} />
        </section>
      </div>
    </main>
  );
}
