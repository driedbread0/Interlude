import { FolderKanban, RotateCcw, Settings2 } from "lucide-react";
import { formatDate, formatDuration, formatPercent, titleCase } from "../../lib/format";

export default function WorkspaceHeader({ result, onNewAnalysis, onOpenProjects }) {
  const project = result?.project || {};
  const key = result?.key || {};
  const correlation = key?.detection?.correlation;

  return (
    <header data-workspace-header className="workspace-header grid grid-cols-[190px_minmax(0,1fr)_auto] items-stretch border-b border-rule-strong bg-porcelain max-lg:grid-cols-[150px_minmax(0,1fr)_auto] max-md:grid-cols-[1fr_auto]">
      <div className="brand-plate border-r border-rule-strong px-5 py-4 max-md:hidden">
        <p>INTERLUDE</p>
        <span>music diagnostic workstation</span>
      </div>

      <div className="min-w-0 px-5 py-3.5">
        <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-teal shadow-[0_0_0_3px_rgba(0,168,135,0.12)]" />
          active diagnostic / {formatDate(project.created_at)}
        </div>
        <div className="mt-1 flex min-w-0 flex-wrap items-end gap-x-4 gap-y-1">
          <h1 className="display-title min-w-0 max-w-full truncate text-3xl leading-none max-sm:text-2xl">{project.title || "Untitled analysis"}</h1>
          <p className="min-w-0 font-mono text-[10px] text-muted">
            {formatDuration(project.duration)} · {Number(project.bpm || 0).toFixed(2)} BPM · {Math.round(project.sample_rate || 0).toLocaleString()} HZ
          </p>
        </div>
      </div>

      <div className="flex min-w-0 items-stretch border-l border-rule-strong">
        <div className="hidden min-w-40 px-4 py-3 text-right sm:block">
          <p className="rule-label">Tonal solution</p>
          <p className="truncate font-display text-sm font-bold">
            {key.root} {titleCase(key.scale_type)}
          </p>
          <p className="font-mono text-[8px] uppercase text-violet">corr. {formatPercent(correlation)}</p>
        </div>
        <button className="workspace-tool" title="Project browser" type="button" onClick={onOpenProjects}>
          <FolderKanban className="h-4 w-4" /><span>projects</span>
        </button>
        <button className="workspace-tool" title="New analysis" type="button" onClick={onNewAnalysis}>
          <RotateCcw className="h-4 w-4" /><span>new</span>
        </button>
        <button className="workspace-tool max-sm:hidden" title="Settings" type="button">
          <Settings2 className="h-4 w-4" /><span>setup</span>
        </button>
      </div>
    </header>
  );
}
