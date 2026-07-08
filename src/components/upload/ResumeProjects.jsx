import { formatDate, formatDuration, formatScore, titleCase } from "../../lib/format";

export default function ResumeProjects({ projects, onOpenProjects, onSelectProject }) {
  return (
    <section className="instrument-panel p-4">
      <div className="mb-3 flex items-center justify-between border-b border-rule pb-3">
        <div>
          <p className="rule-label">Project memory</p>
          <h2 className="display-title text-2xl">Resume work</h2>
        </div>
        <button className="text-sm font-semibold text-cobalt hover:text-cobalt-deep" type="button" onClick={onOpenProjects}>
          Browse
        </button>
      </div>

      <div className="space-y-2">
        {(projects || []).slice(0, 3).map((project) => (
          <button
            key={project.id}
            className="w-full border-l-2 border-cobalt bg-paper px-3 py-3 text-left transition duration-150 ease-instrument hover:bg-[rgba(31,94,255,0.07)]"
            type="button"
            onClick={() => onSelectProject(project.id)}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-display text-base font-bold">{project.title}</p>
                <p className="mt-1 font-mono text-[10px] text-muted">
                  {formatDate(project.created_at)} / {formatDuration(project.duration)}
                </p>
              </div>
              <p className="shrink-0 font-mono text-[10px] text-teal-deep">{formatScore(project.scores?.pitch_accuracy)}</p>
            </div>
            <p className="mt-2 font-mono text-[10px] text-muted">
              {project.key?.root} {titleCase(project.key?.scale_type)}
            </p>
          </button>
        ))}
        {!projects?.length && (
          <p className="text-sm leading-6 text-ink-soft">
            Saved analyses will appear here as reusable projects, with no chat-thread rail.
          </p>
        )}
      </div>
    </section>
  );
}
