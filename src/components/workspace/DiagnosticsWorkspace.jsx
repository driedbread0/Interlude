import { useEffect, useRef } from "react";
import AnalysisBand from "./AnalysisBand";
import DiagnosticRail from "./DiagnosticRail";
import MainSignalDeck from "./MainSignalDeck";
import WorkspaceHeader from "./WorkspaceHeader";
import useAnalysisTransport from "../../hooks/useAnalysisTransport";
import { gsap, useGSAP } from "../../lib/motion";

export default function DiagnosticsWorkspace({ result, onNewAnalysis, onOpenProjects }) {
  const workspaceRef = useRef(null);
  const transport = useAnalysisTransport({ result, scopeRef: workspaceRef });
  const focusKey = `${transport.focusState}:${transport.focusMetric || "none"}:${transport.selectedEvidence?.start ?? ""}`;

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [result?.project?.id]);

  useGSAP(() => {
    const media = gsap.matchMedia();

    media.add(
      {
        fullMotion: "(prefers-reduced-motion: no-preference)",
        compact: "(max-width: 900px)",
      },
      ({ conditions }) => {
        if (!conditions.fullMotion) return;

        const timeline = gsap.timeline({ defaults: { ease: "power3.out" } });
        timeline
          .fromTo("[data-workspace-header]", { y: -18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.42 })
          .fromTo("[data-signal-deck]", { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.58 }, "-=0.22")
          .fromTo("[data-diagnostic-rail]", {
            x: conditions.compact ? 0 : 24,
            y: conditions.compact ? 16 : 0,
            opacity: 0,
          }, {
            x: 0,
            y: 0,
            opacity: 1,
            duration: 0.5,
          }, "-=0.38")
          .fromTo("[data-analysis-band]", { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.48 }, "-=0.32");
      },
    );

    return () => media.revert();
  }, { scope: workspaceRef });

  useGSAP(() => {
    if (!transport.focusMetric || transport.focusState === "recent") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const metric = transport.focusMetric;
    const targets = [
      `[data-focus-stage="metric"][data-evidence-metric="${metric}"]`,
      `[data-focus-stage="signal"]`,
      `[data-focus-stage="chroma"]`,
      `[data-focus-stage="rail"][data-evidence-metric="${metric}"]`,
    ];
    const timeline = gsap.timeline({ defaults: { duration: 0.08, ease: "power2.out" } });

    targets.forEach((selector, index) => {
      timeline.fromTo(
        selector,
        { "--cascade-strength": 0 },
        { "--cascade-strength": 1 },
        index * 0.045,
      );
    });
  }, { dependencies: [focusKey], scope: workspaceRef });

  return (
    <main
      ref={workspaceRef}
      className="analysis-workspace min-h-screen bg-canvas text-ink"
      data-focus-metric={transport.focusMetric || "none"}
      data-focus-state={transport.focusState}
      data-playing={transport.playing ? "true" : "false"}
    >
      <div className="diagnostic-instrument mx-auto min-h-screen max-w-[1720px] bg-paper">
        <WorkspaceHeader result={result} onNewAnalysis={onNewAnalysis} onOpenProjects={onOpenProjects} />

        <section className="grid min-h-0 grid-cols-[minmax(0,1fr)_390px] max-2xl:grid-cols-[minmax(0,1fr)_360px] max-xl:grid-cols-1">
          <div className="min-w-0 border-r border-rule-strong max-xl:border-r-0">
            <MainSignalDeck result={result} transport={transport} />
            <AnalysisBand result={result} transport={transport} />
          </div>

          <DiagnosticRail result={result} transport={transport} />
        </section>
      </div>
    </main>
  );
}
