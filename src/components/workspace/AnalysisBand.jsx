import ChromaLanes from "../visuals/ChromaLanes";
import MetricLaneSuite from "../visuals/MetricLaneSuite";

export default function AnalysisBand({ result }) {
  const metrics = [
    {
      title: "Tempo stability",
      kind: "beat grid",
      points: result?.charts?.tempo,
      color: "#1F5EFF",
    },
    {
      title: "Pitch accuracy",
      kind: "phrase pitch",
      points: result?.charts?.pitch,
      color: "#00A887",
    },
    {
      title: "Harmonic complexity",
      kind: "bar harmony",
      points: result?.charts?.harmony,
      color: "#6E3FF2",
      inverse: true,
    },
    {
      title: "Dynamics contour",
      kind: "RMS trend",
      points: result?.charts?.dynamics,
      color: "#006C5A",
    },
  ];
  const polyphonyRatio = result?.polyphony?.polyphonic_ratio || 0;

  return (
    <section className="grid gap-3">
      <div className="workstation-region overflow-hidden">
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(220px,300px)] gap-4 border-b border-rule bg-paper/88 p-4 max-lg:grid-cols-1">
          <div>
            <p className="rule-label">Primary metric timeline suite</p>
            <h2 className="display-title text-3xl max-sm:text-2xl">Windowed performance map</h2>
          </div>
          <div className="border-l border-rule pl-4 text-right max-lg:border-l-0 max-lg:border-t max-lg:pl-0 max-lg:pt-3 max-lg:text-left">
            <p className="font-mono text-[10px] uppercase text-muted">clocked by beat windows</p>
            <p className="mt-1 text-xs leading-5 text-ink-soft">
              Metric lanes share one timeline so hotspots read as related musical regions.
            </p>
          </div>
        </div>

        <MetricLaneSuite metrics={metrics} />
      </div>

      <div className="workstation-region grid grid-cols-[1fr_300px] gap-0 overflow-hidden max-lg:grid-cols-1">
        <div className="border-r border-rule max-lg:border-r-0 max-lg:border-b">
          <div className="grid grid-cols-[1fr_auto] items-end border-b border-rule bg-porcelain/78 p-4">
            <p className="rule-label">Secondary technical analysis band</p>
            <p className="font-mono text-[10px] text-muted">pitch class lanes</p>
          </div>
          <div className="h-64 border-b border-rule p-3">
            <h3 className="sr-only">Chroma / pitch-class activity</h3>
            <ChromaLanes
              duration={result?.visuals?.chroma?.duration || result?.project?.duration}
              labels={result?.visuals?.chroma?.labels}
              rows={result?.visuals?.chroma?.rows}
            />
          </div>
        </div>

        <div className="grid grid-rows-[auto_1fr] bg-paper">
          <div className="border-b border-rule bg-porcelain/60 p-4">
            <p className="rule-label">Signal interpretation</p>
            <h3 className="display-title text-2xl">Chroma support</h3>
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
            <div className="grid grid-cols-2 border-y border-rule text-center font-mono text-[10px] uppercase text-muted">
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
