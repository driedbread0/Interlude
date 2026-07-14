import { useEffect, useState } from "react";
import UploadPage from "./components/upload/UploadPage";
import DiagnosticsWorkspace from "./components/workspace/DiagnosticsWorkspace";
import ProjectDrawer from "./components/workspace/ProjectDrawer";
import { analyzeFile, deleteProject, fetchOptions, fetchProject, fetchProjects } from "./lib/api";

/*
  Interlude design system implementation:
  - Light layered canvas, cobalt structure, teal signal/analysis, rare violet markers.
  - Bricolage Grotesque for identity and workstation hierarchy; IBM Plex Sans/Mono for data.
  - Three panel roles: signal surfaces, instrument panels, annotation panels.
  - Asymmetric workstation layout centered on signal inspection, not equal dashboard cards.
  - Motion is short, restrained, and tied to upload, drawer, hover, and playback state.
*/

export default function App() {
  const [options, setOptions] = useState({ roots: ["C"], scales: ["major"] });
  const [projects, setProjects] = useState([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [extraPrompt, setExtraPrompt] = useState("");
  const [autoKey, setAutoKey] = useState(true);
  const [root, setRoot] = useState("C");
  const [scaleType, setScaleType] = useState("major");
  const [separateVocals, setSeparateVocals] = useState(false);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchOptions()
      .then((data) => {
        setOptions(data);
        setRoot(data.roots?.[0] || "C");
        setScaleType(data.scales?.includes("major") ? "major" : data.scales?.[0] || "major");
      })
      .catch((apiError) => setError(apiError.message));

    refreshProjects();
  }, []);

  async function refreshProjects() {
    try {
      const data = await fetchProjects();
      setProjects(data.projects || []);
    } catch {
      setProjects([]);
    }
  }

  async function handleAnalyze() {
    if (!selectedFile) return;

    setStatus("analyzing");
    setError("");

    try {
      const analysis = await analyzeFile({
        file: selectedFile,
        extraPrompt,
        root: autoKey ? "auto" : root,
        scaleType: autoKey ? "auto" : scaleType,
        separateVocals,
      });
      setResult(analysis);
      setStatus("workspace");
      await refreshProjects();
    } catch (apiError) {
      setError(apiError.message);
      setStatus("idle");
    }
  }

  async function handleSelectProject(projectId) {
    try {
      const project = await fetchProject(projectId);
      setResult(project);
      setDrawerOpen(false);
      setStatus("workspace");
      setError("");
    } catch (apiError) {
      setError(apiError.message);
    }
  }

  async function handleDeleteProject(projectId) {
    try {
      await deleteProject(projectId);
      setProjects((current) => current.filter((project) => project.id !== projectId));

      if (result?.project?.id === projectId) {
        handleNewAnalysis();
      }
    } catch (apiError) {
      setError(apiError.message);
    }
  }

  function handleNewAnalysis() {
    setResult(null);
    setSelectedFile(null);
    setExtraPrompt("");
    setSeparateVocals(false);
    setStatus("idle");
    setError("");
  }

  return (
    <>
      {result ? (
        <div className="animate-[workspaceIn_320ms_cubic-bezier(0.2,0.8,0.2,1)]">
          <DiagnosticsWorkspace
            result={result}
            onNewAnalysis={handleNewAnalysis}
            onOpenProjects={() => setDrawerOpen(true)}
          />
        </div>
      ) : (
        <div className="animate-[intakeIn_280ms_cubic-bezier(0.2,0.8,0.2,1)]">
          <UploadPage
            options={options}
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            extraPrompt={extraPrompt}
            setExtraPrompt={setExtraPrompt}
            autoKey={autoKey}
            setAutoKey={setAutoKey}
            root={root}
            setRoot={setRoot}
            scaleType={scaleType}
            setScaleType={setScaleType}
            separateVocals={separateVocals}
            setSeparateVocals={setSeparateVocals}
            onAnalyze={handleAnalyze}
            status={status}
            projects={projects}
            onOpenProjects={() => setDrawerOpen(true)}
            onSelectProject={handleSelectProject}
          />
        </div>
      )}

      {error && (
        <div className="fixed bottom-4 left-1/2 z-50 max-w-xl -translate-x-1/2 border border-warning bg-paper px-4 py-3 text-sm font-bold text-warning shadow-panel">
          {error}
        </div>
      )}

      <ProjectDrawer
        open={drawerOpen}
        projects={projects}
        onClose={() => setDrawerOpen(false)}
        onDeleteProject={handleDeleteProject}
        onSelectProject={handleSelectProject}
      />
    </>
  );
}
