export default function AnalysisNoteInput({ value, onChange }) {
  return (
    <section className="border-t border-rule bg-porcelain/55 p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="rule-label">Diagnostic note</p>
        <span className="font-mono text-[10px] uppercase text-muted">optional focus</span>
      </div>
      <textarea
        className="min-h-28 w-full resize-none border-y border-rule bg-paper px-3 py-3 text-sm leading-6 text-ink outline-none transition duration-150 ease-instrument placeholder:text-muted focus:border-cobalt"
        placeholder="Optional focus: chorus tuning, vocal bend handling, groove stability, harmonic language..."
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </section>
  );
}
