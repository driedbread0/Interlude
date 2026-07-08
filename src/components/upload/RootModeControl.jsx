import { SlidersHorizontal } from "lucide-react";
import { titleCase } from "../../lib/format";

export default function RootModeControl({ options, autoKey, setAutoKey, root, setRoot, scaleType, setScaleType }) {
  return (
    <section className="bg-paper p-4">
      <div className="mb-4 flex items-start justify-between gap-3 border-b border-rule pb-3">
        <div className="min-w-0">
          <p className="rule-label">Calibration source</p>
          <h2 className="display-title break-words text-2xl leading-tight">{autoKey ? "Auto detection" : `${root} ${titleCase(scaleType)}`}</h2>
        </div>
        <SlidersHorizontal className="h-5 w-5 shrink-0 text-cobalt" />
      </div>

      <label className="mb-4 grid cursor-pointer grid-cols-[1fr_auto] items-center gap-3 border-y border-rule bg-porcelain/70 px-3 py-3 text-sm font-semibold text-ink-soft">
        <span className="min-w-0">
          <span className="block font-mono text-[10px] uppercase text-muted">key map behavior</span>
          <span className="mt-1 block text-ink">{autoKey ? "Auto-select root and scale/mode" : "Manual key and mode override"}</span>
        </span>
        <span className={`relative h-5 w-10 border transition duration-150 ease-instrument ${autoKey ? "border-cobalt bg-cobalt" : "border-rule-strong bg-paper"}`}>
          <span className={`absolute top-1 h-3 w-3 bg-porcelain transition duration-150 ease-instrument ${autoKey ? "left-6" : "left-1"}`} />
        </span>
        <input
          checked={autoKey}
          className="sr-only"
          type="checkbox"
          onChange={(event) => setAutoKey(event.target.checked)}
        />
      </label>

      <div className="grid grid-cols-[0.72fr_1.28fr] gap-2 max-sm:grid-cols-1">
        <label>
          <span className="rule-label mb-1 block">Root</span>
          <select
            className="h-10 w-full border border-rule bg-porcelain px-2 font-mono text-sm text-ink outline-none transition focus:border-cobalt disabled:bg-paper disabled:text-muted"
            disabled={autoKey}
            value={root}
            onChange={(event) => setRoot(event.target.value)}
          >
            {(options?.roots || ["C"]).map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="rule-label mb-1 block">Scale / mode</span>
          <select
            className="h-10 w-full border border-rule bg-porcelain px-2 text-sm text-ink outline-none transition focus:border-cobalt disabled:bg-paper disabled:text-muted"
            disabled={autoKey}
            value={scaleType}
            onChange={(event) => setScaleType(event.target.value)}
          >
            {(options?.scales || ["major"]).map((item) => (
              <option key={item} value={item}>
                {titleCase(item)}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
