import { FolderKanban, RotateCcw, Settings2 } from "lucide-react";
import { formatDate, formatDuration, titleCase } from "../../lib/format";

export default function WorkspaceHeader({ result, onNewAnalysis, onOpenProjects }) {
  const project = result?.project || {};
  const key = result?.key || {};

  return (
    <header className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 border-b border-rule-strong bg-porcelain px-5 py-4 max-md:grid-cols-1">
      <div className="min-w-0">
        <p className="rule-label">Project / active diagnostic</p>
        <div className="mt-1 flex min-w-0 flex-wrap items-end gap-x-4 gap-y-2">
          <h1 className="display-title min-w-0 max-w-full truncate text-4xl leading-none max-sm:text-3xl">{project.title || "Untitled analysis"}</h1>
          <p className="min-w-0 font-mono text-xs text-muted">
            {formatDate(project.created_at)} / {formatDuration(project.duration)} / {Math.round(project.bpm || 0)} BPM
          </p>
        </div>
      </div>

      <div className="flex min-w-0 items-stretch gap-2">
        <div className="hidden max-w-48 border border-rule bg-paper px-3 py-2 text-right sm:block">
          <p className="rule-label">Key state</p>
          <p className="truncate font-display text-sm font-bold">
            {key.root} {titleCase(key.scale_type)} <span className="font-mono text-[10px] text-muted">({key.mode})</span>
          </p>
        </div>
        <button className="hard-button grid w-11 place-items-center px-0" title="Project browser" type="button" onClick={onOpenProjects}>
          <FolderKanban className="h-5 w-5" />
        </button>
        <button className="hard-button grid w-11 place-items-center px-0" title="New analysis" type="button" onClick={onNewAnalysis}>
          <RotateCcw className="h-5 w-5" />
        </button>
        <button className="hard-button grid w-11 place-items-center px-0" title="Settings" type="button">
          <Settings2 className="h-5 w-5" />
        </button>
      </div>
    </header>
  );
}
