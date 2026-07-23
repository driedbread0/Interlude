import { ArrowUpRight } from "lucide-react";
import { formatDate, formatDuration, formatPercent, formatScore, titleCase } from "../../lib/format";
import WaveformCanvas from "../visuals/WaveformCanvas";

function dominantMetric(scores = {}) {
  const entries = [
    ["tempo", scores.tempo_stability],
    ["pitch", scores.pitch_accuracy],
    ["harmony", scores.harmonic_complexity],
    ["dynamics", scores.dynamics_variation],
  ].filter(([, value]) => Number.isFinite(Number(value)));
  if (!entries.length) return ["unrated", null];
  return entries.reduce((best, entry) => Number(entry[1]) > Number(best[1]) ? entry : best);
}

export default function ResumeProjects({ projects, onOpenProjects, onSelectProject }) {
  return (
    <section className="resume-console border-t border-rule-strong">
      <div className="flex items-end justify-between border-b border-rule px-4 py-3">
        <div><p className="rule-label">Project memory</p><h2 className="display-title text-2xl">Resume inspection</h2></div>
        <button className="font-mono text-[9px] uppercase text-cobalt hover:text-cobalt-deep" type="button" onClick={onOpenProjects}>all projects</button>
      </div>

      <div className="divide-y divide-rule">
        {(projects || []).slice(0, 3).map((project) => {
          const [dominant, value] = dominantMetric(project.scores);
          return (
            <button key={project.id} className="resume-project" type="button" onClick={() => onSelectProject(project.id)}>
              <div className="resume-project-wave"><WaveformCanvas quiet height={48} /></div>
              <div className="min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate font-display text-sm font-bold">{project.title}</p><ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-cobalt" />
                </div>
                <p className="mt-1 font-mono text-[8px] uppercase text-muted">{formatDate(project.created_at)} · {formatDuration(project.duration)}</p>
                <div className="mt-2 flex items-center justify-between gap-2 font-mono text-[8px] uppercase">
                  <span className="text-violet">{project.key?.root} {titleCase(project.key?.scale_type)}</span>
                  <span className="text-muted">{dominant} {formatScore(value)}</span>
                  <span className="text-teal-deep">corr. {formatPercent(project.key?.detection?.correlation)}</span>
                </div>
              </div>
            </button>
          );
        })}
        {!projects?.length && <p className="p-4 text-sm leading-6 text-ink-soft">Saved analyses will appear here with tonal confidence and signal identity.</p>}
      </div>
    </section>
  );
}
