import { Check, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { formatDate, formatDuration, formatScore, titleCase } from "../../lib/format";
import WaveformCanvas from "../visuals/WaveformCanvas";
import { gsap, useGSAP } from "../../lib/motion";

function ScorePreview({ label, value, color }) {
  const normalized = Math.max(0, Math.min(1, Number(value) || 0));

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2 font-mono text-[9px] uppercase text-muted">
        <span>{label}</span>
        <span>{formatScore(value)}</span>
      </div>
      <div className="h-1.5 bg-rule">
        <div className="h-full" style={{ width: `${normalized * 100}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

export default function ProjectDrawer({ open, projects, onClose, onDeleteProject, onSelectProject }) {
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const drawerRef = useRef(null);
  const panelRef = useRef(null);

  useGSAP(() => {
    if (!drawerRef.current || !panelRef.current) return;

    if (open) {
      gsap.set(drawerRef.current, { autoAlpha: 1 });
      gsap.fromTo(drawerRef.current, { backgroundColor: "rgba(17,20,24,0)" }, { backgroundColor: "rgba(17,20,24,0.32)", duration: 0.28 });
      gsap.fromTo(panelRef.current, { xPercent: 100 }, { xPercent: 0, duration: 0.46, ease: "power3.out" });
    } else {
      gsap.to(panelRef.current, { xPercent: 100, duration: 0.32, ease: "power2.in" });
      gsap.to(drawerRef.current, { autoAlpha: 0, duration: 0.32 });
    }
  }, { dependencies: [open], scope: drawerRef });

  async function confirmDelete(projectId) {
    setDeletingId(projectId);

    try {
      await onDeleteProject(projectId);
      setConfirmDeleteId(null);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div
      ref={drawerRef}
      aria-hidden={!open}
      className={`fixed inset-0 z-50 invisible ${open ? "pointer-events-auto" : "pointer-events-none"}`}
      onClick={onClose}
    >
      <aside
        ref={panelRef}
        className="project-drawer-panel absolute right-0 top-0 h-full w-full max-w-[620px] bg-paper shadow-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-rule bg-porcelain p-5">
          <div>
            <p className="rule-label">Project browser</p>
            <h2 className="display-title text-3xl">Saved analyses</h2>
          </div>
          <button className="hard-button grid h-10 w-10 place-items-center px-0" type="button" onClick={onClose}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="h-[calc(100%-85px)] divide-y divide-rule overflow-auto">
          {!projects?.length && (
            <p className="p-5 text-sm leading-6 text-ink-soft">
              No projects have been analyzed in this local session yet.
            </p>
          )}
          {projects?.map((project) => {
            const confirming = confirmDeleteId === project.id;
            const deleting = deletingId === project.id;

            return (
            <article
              key={project.id}
              className="group bg-porcelain transition duration-150 ease-instrument hover:bg-[rgba(31,94,255,0.06)]"
            >
              <div className="grid grid-cols-[1fr_150px] gap-0 max-sm:grid-cols-1">
                <button
                  className="min-w-0 p-4 text-left"
                  type="button"
                  onClick={() => onSelectProject(project.id)}
                >
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h3 className="truncate font-display text-xl font-bold">{project.title}</h3>
                      <p className="mt-1 font-mono text-[10px] text-muted">
                        {formatDate(project.created_at)} / {formatDuration(project.duration)}
                      </p>
                    </div>
                    <div className="h-7 w-7 border border-cobalt bg-paper transition group-hover:bg-cobalt" />
                  </div>
                  <div className="h-14 border border-rule bg-paper">
                    <WaveformCanvas quiet height={60} />
                  </div>
                </button>

                <div className="border-l border-rule bg-paper p-4 max-sm:border-l-0 max-sm:border-t">
                  <div className="mb-4 text-right max-sm:text-left">
                    <p className="rule-label">Key state</p>
                    <p className="font-display text-base font-bold">
                      {project.key?.root || "—"} {titleCase(project.key?.scale_type)}
                    </p>
                    <p className="font-mono text-[10px] text-muted">{project.key?.mode || "saved analysis"}</p>
                    <p className="mt-1 font-mono text-[8px] uppercase text-teal-deep">
                      corr. {formatScore(project.key?.detection?.correlation)}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <ScorePreview label="tempo" value={project.scores?.tempo_stability} color="#00A887" />
                    <ScorePreview label="pitch" value={project.scores?.pitch_accuracy} color="#006C5A" />
                    <ScorePreview label="harm" value={project.scores?.harmonic_complexity} color="#6E3FF2" />
                  </div>
                  <div className="mt-4 border-t border-rule pt-3">
                    {confirming ? (
                      <div className="grid gap-2">
                        <button
                          className="flex items-center justify-center gap-2 border border-warning bg-paper px-2 py-2 font-mono text-[10px] font-bold uppercase text-warning transition hover:bg-warning hover:text-porcelain disabled:cursor-wait disabled:opacity-60"
                          disabled={deleting}
                          type="button"
                          onClick={() => confirmDelete(project.id)}
                        >
                          <Check className="h-3.5 w-3.5" />
                          {deleting ? "Deleting" : "Confirm delete"}
                        </button>
                        <button
                          className="border border-rule bg-porcelain px-2 py-2 font-mono text-[10px] font-bold uppercase text-muted transition hover:border-cobalt hover:text-cobalt"
                          disabled={deleting}
                          type="button"
                          onClick={() => setConfirmDeleteId(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        className="flex w-full items-center justify-center gap-2 border border-rule bg-porcelain px-2 py-2 font-mono text-[10px] font-bold uppercase text-muted transition hover:border-warning hover:text-warning"
                        type="button"
                        onClick={() => setConfirmDeleteId(project.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </article>
            );
          })}
        </div>
      </aside>
    </div>
  );
}
