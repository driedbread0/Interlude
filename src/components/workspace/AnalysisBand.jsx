import ChromaLanes from "../visuals/ChromaLanes";
import MetricLaneSuite from "../visuals/MetricLaneSuite";
import HarmonicComplexityPanel from "./HarmonicComplexityPanel";

export default function AnalysisBand({ result, transport }) {
  const scores = result?.scores || {};
  const metrics = [
    {
      key: "tempo",
      title: "Tempo stability",
      kind: "beat grid",
      points: result?.charts?.tempo,
      score: scores.tempo_stability,
      color: "#00A887",
    },
    {
      key: "pitch",
      title: "Pitch accuracy",
      kind: "phrase pitch",
      points: result?.charts?.pitch,
      score: scores.pitch_accuracy,
      color: "#006C5A",
      emptyLabel: "no reliable pitch windows",
    },
    {
      key: "harmony",
      title: "Harmonic complexity",
      kind: "bar harmony",
      points: result?.charts?.harmony,
      score: scores.harmonic_complexity,
      color: "#6E3FF2",
      inverse: true,
    },
    {
      key: "dynamics",
      title: "Dynamics contour",
      kind: "RMS trend",
      points: result?.charts?.dynamics,
      score: scores.dynamics_variation,
      color: "#00A887",
    },
  ];
  const polyphonyRatio = result?.polyphony?.polyphonic_ratio || 0;

  return (
    <section data-analysis-band className="analysis-band bg-paper">
      <div className="analysis-timeline-register overflow-hidden">
        <div className="analysis-band-heading grid grid-cols-[minmax(0,1fr)_minmax(220px,330px)] gap-4 px-5 py-5 max-lg:grid-cols-1">
          <div>
            <p className="rule-label">Analysis band / source-linked channels</p>
            <h2 className="display-title text-[1.65rem] max-sm:text-2xl">Windowed performance map</h2>
          </div>
          <div className="analysis-band-note pl-4 text-right max-lg:pl-0 max-lg:text-left">
            <p className="font-mono text-[10px] uppercase text-muted">clocked by beat windows</p>
            <p className="mt-1 text-xs leading-5 text-ink-soft">
              Hover any channel to carry the same analysis cursor through every evidence surface.
            </p>
          </div>
        </div>

        <MetricLaneSuite metrics={metrics} transport={transport} />
        <HarmonicComplexityPanel result={result} activeWindow={transport.activeWindows.harmony} />
      </div>

      <div className="chroma-register grid grid-cols-[1fr_300px] gap-0 overflow-hidden max-lg:grid-cols-1">
        <div className="chroma-register-plot">
          <div className="grid grid-cols-[1fr_auto] items-end p-4">
            <p className="rule-label">Harmonic support register</p>
            <p className="font-mono text-[10px] text-muted">pitch class lanes</p>
          </div>
          <div className="h-64 px-3 pb-3">
            <h3 className="sr-only">Chroma / pitch-class activity</h3>
            <ChromaLanes
              duration={result?.visuals?.chroma?.duration || result?.project?.duration}
              labels={result?.visuals?.chroma?.labels}
              rows={result?.visuals?.chroma?.rows}
              transport={transport}
            />
          </div>
        </div>

        <div className="chroma-support-copy grid grid-rows-[auto_1fr] bg-paper">
          <div className="p-4">
            <p className="rule-label">Supporting register</p>
            <h3 className="font-body text-base font-semibold text-ink">Chroma support</h3>
          </div>
          <div className="grid content-start gap-4 p-4">
            <div className="border-y border-rule py-3">
              <div className="mb-2 flex items-center justify-between font-mono text-[10px] uppercase text-muted">
                <span>polyphonic density</span>
                <span>{Math.round(polyphonyRatio * 100)}%</span>
              </div>
              <div className="h-2 bg-porcelain">
                <div className="h-full bg-teal" style={{ width: `${Math.min(100, Math.round(polyphonyRatio * 100))}%` }} />
              </div>
            </div>
            <div className="chroma-evidence-pair grid grid-cols-2 text-center font-mono text-[10px] uppercase text-muted">
              <div className="border-r border-rule px-2 py-3">
                <p className="text-ink">tracker</p>
                <p className="mt-1 text-teal-deep">{result?.polyphony?.warning ? "caution" : "clear"}</p>
              </div>
              <div className="px-2 py-3">
                <p className="text-ink">evidence</p>
                <p className="mt-1 text-cobalt-deep">supporting</p>
              </div>
            </div>
            <p className="text-xs leading-5 text-ink-soft">
              {result?.polyphony?.warning
                ? "Pitch tracking should be interpreted carefully because dense simultaneous pitch activity was detected."
                : "Pitch tracking did not flag heavy polyphonic density, so phrase windows are more useful."}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
