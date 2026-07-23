import { Activity, AudioLines, Crosshair, Gauge, Send, Sparkles, Volume2, Waves } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { askFollowUp } from "../../lib/api";
import { formatDuration, formatPercent, formatScore, normalizeDiagnosticText, titleCase } from "../../lib/format";
import { gsap, useGSAP } from "../../lib/motion";

function windowTime(window) {
  if (!window) return "not mapped";
  return window.time_range || `${formatDuration(window.start)}–${formatDuration(window.end)}`;
}

function valueForWindow(window, fallbacks = []) {
  for (const key of ["score", ...fallbacks]) {
    const value = Number(window?.[key]);
    if (Number.isFinite(value)) return value;
  }
  return null;
}

function ScoreRow({ metricKey, label, value, icon: Icon, accent, detail, active }) {
  const percent = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, Number(value) * 100));

  return (
    <div
      className={`metric-register-row focus-reactive ${active ? "is-active" : ""}`}
      data-evidence-metric={metricKey}
      data-focus-stage="rail"
    >
      <Icon className="h-3.5 w-3.5" style={{ color: accent }} />
      <div className="min-w-0">
        <div className="flex items-baseline justify-between gap-3">
          <p>{label}</p><strong>{formatScore(value)}</strong>
        </div>
        <div className="mt-1.5 h-1 bg-rule/70"><div className="h-full" style={{ width: `${percent}%`, backgroundColor: accent }} /></div>
        <span>{detail}</span>
      </div>
    </div>
  );
}

function strongestPoint(points, strategy = "max") {
  const usable = (points || []).filter((point) => Number.isFinite(Number(point?.y)) && !point?.ambiguous);
  if (!usable.length) return null;
  return usable.reduce((best, point) => strategy === "min"
    ? (Number(point.y) < Number(best.y) ? point : best)
    : (Number(point.y) > Number(best.y) ? point : best));
}

export default function DiagnosticRail({ result, transport }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const regionRef = useRef(null);
  const key = result?.key || {};
  const detection = key.detection || {};
  const scores = result?.scores || {};
  const diagnosticText = normalizeDiagnosticText(result?.response) || "Recommendations appear after analysis.";
  const { activeWindows, evidenceTime, selectEvidence, selectedEvidence } = transport;
  const harmonicWindowStart = activeWindows.harmony?.start;
  const metricRows = [
    { key: "tempo", label: "Tempo stability", value: scores.tempo_stability, icon: Gauge, accent: "#00A887", detail: "beat interval lock" },
    { key: "pitch", label: "Pitch accuracy", value: scores.pitch_accuracy, icon: Activity, accent: "#00A887", detail: `${result?.pitch_tracking?.reliability || "unknown"} reliability` },
    { key: "harmony", label: "Harmonic complexity", value: scores.harmonic_complexity, icon: Waves, accent: "#6E3FF2", detail: "composite harmonic evidence" },
    { key: "dynamics", label: "Dynamics contour", value: scores.dynamics_variation, icon: Volume2, accent: "#006C5A", detail: "RMS movement" },
  ];

  const evidenceAnchors = useMemo(() => [
    { metric: "tempo", title: "Weakest beat lock", point: strongestPoint(result?.charts?.tempo, "min"), color: "#00A887" },
    { metric: "harmony", title: "Highest harmonic load", point: strongestPoint(result?.charts?.harmony), color: "#6E3FF2" },
  ].filter((anchor) => anchor.point), [result?.charts]);

  useGSAP(() => {
    if (!regionRef.current) return;
    gsap.fromTo(regionRef.current, { backgroundColor: "rgba(31, 94, 255, 0.12)" }, {
      backgroundColor: "rgba(31, 94, 255, 0)",
      duration: 0.7,
      ease: "power2.out",
    });
  }, { dependencies: [harmonicWindowStart, selectedEvidence?.start], scope: regionRef });

  async function submit(event) {
    event.preventDefault();
    const trimmed = question.trim();

    if (!trimmed || !result?.project?.id) return;

    setQuestion("");
    setMessages((current) => [...current, { role: "user", text: trimmed }]);
    setBusy(true);

    try {
      const reply = await askFollowUp(result.project.id, trimmed);
      setMessages((current) => [...current, { role: "assistant", text: reply.response, error: Boolean(reply.api_error) }]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", text: error.message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside data-diagnostic-rail className="diagnostic-rail min-h-0 bg-paper">
      <section className="console-group console-interpretation">
        <div className="console-group-heading flex items-center justify-between">
          <p className="rule-label">Interpretation / tonal center</p>
          <AudioLines className="h-4 w-4 text-violet" />
        </div>
        <div className="key-console-hero">
          <div>
            <span>detected key</span>
            <h2>{key.root || "—"} <em>{titleCase(key.scale_type)}</em></h2>
          </div>
          <strong>{formatPercent(detection.correlation)}</strong>
        </div>
        <div className="key-console-grid">
          <div><span>method</span><strong>{detection.algorithm ? "KS correlation" : key.mode || "auto"}</strong></div>
          <div><span>runner-up margin</span><strong>{formatScore(detection.runner_up_margin)}</strong></div>
          <div><span>scale energy fit</span><strong>{formatPercent(key.fit)}</strong></div>
        </div>
        <div className="interpretation-premise">
          <p className="rule-label">Diagnostic premise</p>
          <p className="interpretation-summary">{result?.summary}</p>
        </div>
      </section>

      <section className="console-group console-evidence">
        <div className="console-group-heading flex items-center justify-between">
          <p className="rule-label">Evidence / source-linked register</p>
          <span className="font-mono text-[10px] text-cobalt-deep">{formatDuration(evidenceTime)}</span>
        </div>
        <div ref={regionRef} className="current-region-console">
          <div className="current-region-grid">
            <div className="focus-reactive" data-focus-stage="rail" data-evidence-metric="tempo"><span>tempo</span><strong>{formatScore(valueForWindow(activeWindows.tempo))}</strong><small>{windowTime(activeWindows.tempo)}</small></div>
            <div className="focus-reactive" data-focus-stage="rail" data-evidence-metric="pitch"><span>pitch</span><strong>{formatScore(valueForWindow(activeWindows.pitch))}</strong><small>{activeWindows.pitch?.reliability || result?.pitch_tracking?.reliability || "unrated"}</small></div>
            <div className={`focus-reactive ${activeWindows.harmony?.ambiguous ? "is-ambiguous" : ""}`} data-focus-stage="rail" data-evidence-metric="harmony"><span>harmony</span><strong>{activeWindows.harmony?.ambiguous ? "?" : formatScore(valueForWindow(activeWindows.harmony, ["harmonic_complexity"]))}</strong><small>{activeWindows.harmony?.ambiguous ? "low-confidence evidence" : activeWindows.harmony?.evidence_label || windowTime(activeWindows.harmony)}</small></div>
            <div className="focus-reactive" data-focus-stage="rail" data-evidence-metric="dynamics"><span>dynamics</span><strong>{formatScore(valueForWindow(activeWindows.dynamics))}</strong><small>{windowTime(activeWindows.dynamics)}</small></div>
          </div>
        </div>
        <div className="metric-register">
          <div className="metric-register-heading"><p className="rule-label">Global metric register</p><span>0–1</span></div>
          {metricRows.map(({ key: metricKey, ...metric }) => (
            <ScoreRow key={metricKey} metricKey={metricKey} {...metric} active={selectedEvidence?.metric === metricKey} />
          ))}
        </div>
      </section>

      <section className="console-group console-action">
        <div className="console-group-heading flex items-start justify-between gap-3">
          <div><p className="rule-label">Action / musical reading</p><h3>What the evidence suggests</h3></div>
          {result?.api_error && <span className="diagnostic-warning">API warning</span>}
        </div>
        <div className="recommendation-readout">
          <div className="recommendation-heading"><Sparkles className="h-3.5 w-3.5" /><span>musical interpretation</span></div>
          <div>{diagnosticText}</div>
        </div>
        <div className="evidence-anchor-list">
          {evidenceAnchors.map((anchor) => (
            <button
              key={anchor.metric}
              type="button"
              className="focus-reactive"
              data-evidence-metric={anchor.metric}
              data-focus-stage="rail"
              onClick={() => selectEvidence({ ...anchor.point, metric: anchor.metric, metricTitle: anchor.title, color: anchor.color }, true)}
            >
              <Crosshair className="h-3.5 w-3.5" />
              <span>{anchor.title}</span>
              <strong>{windowTime(anchor.point)}</strong>
            </button>
          ))}
        </div>

        <div className="followup-console">
          <div><p className="rule-label">Follow-up instrument</p><h3>Interrogate this analysis</h3></div>
          <div className="followup-messages">
            {!messages.length && <p>Ask about a passage, metric, or relationship in this project.</p>}
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={`${message.role} ${message.error ? "error" : ""}`}>
                {normalizeDiagnosticText(message.text)}
              </div>
            ))}
          </div>
          <form onSubmit={submit}>
            <textarea
              placeholder="Ask about the current evidence…"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button disabled={busy || !question.trim()} type="submit" aria-label="Send follow-up"><Send className="h-4 w-4" /></button>
          </form>
        </div>
      </section>
    </aside>
  );
}
