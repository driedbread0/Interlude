import { AudioLines, FolderKanban } from "lucide-react";

export default function BrandMasthead({ onOpenProjects }) {
  return (
    <header className="flex items-start justify-between gap-6 border-b border-rule-strong pb-5 max-sm:flex-wrap">
      <div className="flex min-w-0 items-start gap-4">
        <div className="grid h-14 w-14 shrink-0 place-items-center border border-cobalt bg-paper text-cobalt shadow-insetline">
          <AudioLines className="h-7 w-7" />
        </div>
        <div className="min-w-0">
          <p className="rule-label">Music diagnostic workstation</p>
          <h1 className="display-title text-5xl leading-none max-sm:text-4xl">Interlude</h1>
        </div>
      </div>

      <button className="hard-button flex shrink-0 items-center gap-2" type="button" onClick={onOpenProjects}>
        <FolderKanban className="h-4 w-4" />
        Projects
      </button>
    </header>
  );
}
