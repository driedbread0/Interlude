import { AudioLines, FolderKanban } from "lucide-react";

export default function BrandMasthead({ onOpenProjects }) {
  return (
    <header data-intake-masthead className="flex items-center justify-between gap-6 border-x border-t border-rule-strong bg-porcelain px-5 py-3 max-sm:flex-wrap max-sm:border-x-0">
      <div className="flex min-w-0 items-start gap-4">
        <div className="grid h-10 w-10 shrink-0 place-items-center bg-cobalt text-porcelain">
          <AudioLines className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="rule-label">Music diagnostic workstation</p>
          <h1 className="display-title text-2xl leading-none">Interlude</h1>
        </div>
      </div>

      <button className="hard-button flex shrink-0 items-center gap-2" type="button" onClick={onOpenProjects}>
        <FolderKanban className="h-4 w-4" />
        Projects
      </button>
    </header>
  );
}
