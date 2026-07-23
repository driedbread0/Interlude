import { formatPercent, formatScore, titleCase } from "../../lib/format";

function ComponentReadout({ label, value, weight, detail, color }) {
  const percent = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, Number(value) * 100));

  return (
    <div className="min-w-0 bg-paper/80 px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase text-muted">{label}</p>
          <p className="mt-1 text-xs leading-5 text-ink-soft">{detail}</p>
        </div>
        <span className="shrink-0 font-mono text-[9px] text-muted">×{Number(weight || 0).toFixed(2)}</span>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="h-1.5 min-w-0 flex-1 bg-porcelain">
          <div className="h-full" style={{ width: `${percent}%`, backgroundColor: color }} />
        </div>
        <span className="technical-value text-lg">{formatScore(value)}</span>
      </div>
    </div>
  );
}

export default function HarmonicComplexityPanel({ result, activeWindow }) {
  const analysis = result?.harmonic_analysis || {};
  const components = analysis.components || {};
  const weights = analysis.weights || {};
  const confidence = analysis.confidence || {};
  const modulation = analysis.modulation || {};
  const movement = analysis.movement || {};
  const scores = result?.scores || {};
  const rawDeviation = components.diatonic_deviation ?? scores.diatonic_deviation ?? scores.raw_harmonic_complexity;
  const adjustedDeviation = components.adjusted_diatonic_deviation;
  const tonalStability = components.tonal_stability ?? scores.tonal_stability;
  const tonalInstability = components.tonal_instability ?? (
    tonalStability === null || tonalStability === undefined ? undefined : 1 - Number(tonalStability)
  );
  const componentRows = [
    {
      label: "Diatonic deviation",
      value: rawDeviation,
      weight: weights.diatonic_deviation ?? 0.08,
      detail: adjustedDeviation === null || adjustedDeviation === undefined
        ? "Pitch energy outside the analysis key."
        : `Composite uses ${formatScore(adjustedDeviation)} after modulation confidence.`,
      color: "#6E3FF2",
    },
    {
      label: "Harmonic movement",
      value: components.harmonic_movement ?? scores.harmonic_movement,
      weight: weights.harmonic_movement ?? 0.34,
      detail: "Chord-region change rate and novelty.",
      color: "#6E3FF2",
    },
    {
      label: "Tonal instability",
      value: tonalInstability,
      weight: weights.tonal_instability ?? 0.07,
      detail: `Centered-key stability ${formatScore(tonalStability)}.`,
      color: "#8A3FFC",
    },
    {
      label: "Voicing density",
      value: components.voicing_density ?? scores.voicing_density,
      weight: weights.voicing_density ?? 0.03,
      detail: "Effective simultaneous pitch-class activity.",
      color: "#4F46B8",
    },
    {
      label: "Modulation load",
      value: components.modulation_load ?? scores.modulation_load,
      weight: weights.modulation_load ?? 0.16,
      detail: "Confident key-change frequency, duration, and breadth.",
      color: "#4F46B8",
    },
    {
      label: "Harmonic color",
      value: components.harmonic_color ?? scores.harmonic_color,
      weight: weights.harmonic_color ?? 0.32,
      detail: "Sevenths, added notes, altered dominants, and diminished color.",
      color: "#8A3FFC",
    },
  ];
  const dominant = (analysis.dominant_factors || []).map(titleCase).join(" / ") || "Compatibility result";
  const ambiguousWindows = confidence.ambiguous_window_count;
  const totalWindows = result?.windows?.harmony?.length || 0;

  return (
    <section className="harmonic-component-register bg-porcelain/45">
      <div className="harmonic-component-heading grid grid-cols-[minmax(0,1fr)_300px] max-lg:grid-cols-1">
        <div className="min-w-0 px-4 py-3">
          <p className="rule-label">Harmonic component register</p>
          <div className="mt-1 flex flex-wrap items-end justify-between gap-3">
            <h3 className="font-body text-base font-semibold text-ink">Composite evidence assembly</h3>
            <span className="font-mono text-[10px] uppercase text-violet">driver: {dominant}</span>
          </div>
        </div>
        <div className="border-l border-rule px-4 py-3 font-mono text-[10px] text-muted max-lg:border-l-0 max-lg:border-t">
          <div className="flex justify-between gap-3">
            <span>composite</span>
            <strong className="text-violet">{formatScore(scores.harmonic_complexity)}</strong>
          </div>
          <div className="mt-1 flex justify-between gap-3">
            <span>evidence before curve</span>
            <span>{formatScore(analysis.evidence_score ?? scores.harmonic_evidence_score)}</span>
          </div>
          <div className="mt-1 flex justify-between gap-3">
            <span>analyzable windows</span>
            <span>{formatPercent(confidence.analyzable_duration_ratio)}</span>
          </div>
        </div>
      </div>

      <div className="harmonic-component-grid grid grid-cols-3 max-md:grid-cols-2 max-sm:grid-cols-1">
        {componentRows.map((component) => (
          <ComponentReadout key={component.label} {...component} />
        ))}
      </div>

      <div className="grid grid-cols-7 bg-paper/70 font-mono text-[10px] text-muted max-xl:grid-cols-4 max-lg:grid-cols-2 max-sm:grid-cols-1">
        <div className="border-r border-rule px-3 py-2">
          <span className="block uppercase">global key corr.</span>
          <strong className="mt-1 block text-ink">{formatScore(confidence.global_key_correlation)}</strong>
        </div>
        <div className="border-r border-rule px-3 py-2">
          <span className="block uppercase">runner-up margin</span>
          <strong className="mt-1 block text-ink">{formatScore(confidence.global_key_correlation_margin)}</strong>
        </div>
        <div className="border-r border-rule px-3 py-2">
          <span className="block uppercase">modulation runs</span>
          <strong className="mt-1 block text-ink">{modulation.runs?.length ?? 0}</strong>
        </div>
        <div className="border-r border-rule px-3 py-2">
          <span className="block uppercase">chord changes</span>
          <strong className="mt-1 block text-ink">{movement.chord_change_count ?? "--"}</strong>
        </div>
        <div className="border-r border-rule px-3 py-2">
          <span className="block uppercase">colored regions</span>
          <strong className="mt-1 block text-ink">{formatPercent(movement.colored_chord_ratio)}</strong>
        </div>
        <div className="border-r border-rule px-3 py-2">
          <span className="block uppercase">altered regions</span>
          <strong className="mt-1 block text-ink">{formatPercent(movement.altered_chord_ratio)}</strong>
        </div>
        <div className={`px-3 py-2 ${ambiguousWindows ? "bg-[rgba(110,63,242,0.08)] text-violet" : ""}`}>
          <span className="block uppercase">uncertain evidence</span>
          <strong className="mt-1 block">{ambiguousWindows ?? "--"} / {totalWindows || "--"} windows</strong>
        </div>
      </div>
      {activeWindow && (
        <div className={`harmonic-live-readout ${activeWindow.ambiguous ? "is-ambiguous" : ""}`}>
          <span>cursor evidence</span>
          <strong>{activeWindow.time_range || `${Number(activeWindow.start || 0).toFixed(1)}–${Number(activeWindow.end || 0).toFixed(1)}s`}</strong>
          <span>{activeWindow.ambiguous ? "low-confidence harmonic evidence" : activeWindow.evidence_label || activeWindow.local_key_label || "harmonic window"}</span>
          <strong>{activeWindow.ambiguous ? "AMBIGUOUS" : formatScore(activeWindow.score ?? activeWindow.harmonic_complexity)}</strong>
        </div>
      )}
    </section>
  );
}
