import { Activity, AudioLines, Gauge, Send, Volume2, Waves } from "lucide-react";
import { useState } from "react";
import { askFollowUp } from "../../lib/api";
import { formatPercent, formatScore, normalizeDiagnosticText, titleCase } from "../../lib/format";

function ScoreRow({ label, value, icon: Icon, accent, detail }) {
  const percent = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, Number(value) * 100));

  return (
    <div className="grid grid-cols-[1fr_76px] items-center gap-3 py-3">
      <div className="min-w-0">
        <div className="mb-2 flex items-center gap-2">
          <Icon className="h-3.5 w-3.5 shrink-0" style={{ color: accent }} />
          <p className="truncate text-sm font-semibold text-ink">{label}</p>
        </div>
        <div className="h-1.5 bg-porcelain">
          <div className="h-full" style={{ width: `${percent}%`, backgroundColor: accent }} />
        </div>
        <p className="mt-1 font-mono text-[10px] uppercase text-muted">{detail}</p>
      </div>
      <p className="technical-value text-right text-xl">{formatScore(value)}</p>
    </div>
  );
}

export default function DiagnosticRail({ result }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const key = result?.key || {};
  const scores = result?.scores || {};
  const diagnosticText = normalizeDiagnosticText(result?.response) || "Recommendations appear after analysis.";
  const metricRows = [
    { label: "Tempo stability", value: scores.tempo_stability, icon: Gauge, accent: "#1F5EFF", detail: "beat lock" },
    { label: "Pitch accuracy", value: scores.pitch_accuracy, icon: Activity, accent: "#00A887", detail: "phrase trace" },
    { label: "Harmony complexity", value: scores.harmonic_complexity, icon: Waves, accent: "#6E3FF2", detail: "key relation" },
    { label: "Dynamics contour", value: scores.dynamics_variation, icon: Volume2, accent: "#006C5A", detail: "RMS trend" },
  ];

  async function submit(event) {
    event.preventDefault();
    const trimmed = question.trim();

    if (!trimmed || !result?.project?.id) return;

    setQuestion("");
    setMessages((current) => [...current, { role: "user", text: trimmed }]);
    setBusy(true);

    try {
      const reply = await askFollowUp(result.project.id, trimmed);
      setMessages((current) => [
        ...current,
        { role: "assistant", text: reply.response, error: Boolean(reply.api_error) },
      ]);
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", text: error.message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="workstation-region min-h-0 overflow-auto bg-paper">
      <section className="border-b border-rule-strong bg-porcelain/80 p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="rule-label">Diagnostic console</p>
          <span className="font-mono text-[10px] uppercase text-muted">project readout</span>
        </div>
        <div className="border-l-4 border-cobalt bg-[rgba(31,94,255,0.08)] p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-bold text-cobalt-deep">Detected key / mode</p>
              <p className="display-title mt-1 break-words text-3xl leading-tight">
                {key.root} {titleCase(key.scale_type)}
              </p>
            </div>
            <AudioLines className="h-5 w-5 shrink-0 text-cobalt" />
          </div>
          <div className="mt-3 grid grid-cols-2 border-t border-cobalt/20 pt-3 font-mono text-[10px] text-cobalt-deep">
            <span>{key.mode || "auto"}</span>
            <span className="text-right">fit {formatPercent(key.fit)}</span>
          </div>
        </div>
      </section>

      <div className="divide-y divide-rule">
        <section className="min-h-0 bg-porcelain/74 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="rule-label">Written diagnostics</p>
              <h3 className="display-title text-3xl leading-tight">Recommendations</h3>
            </div>
            {result?.api_error && (
              <span className="border border-warning bg-paper px-2 py-1 font-mono text-[10px] text-warning">
                API warning
              </span>
            )}
          </div>
          <div className="border-l-4 border-teal bg-paper px-4 py-3 shadow-crisp">
            <p className="mb-2 font-mono text-[10px] uppercase text-teal-deep">takeaway</p>
            <div className="max-h-[320px] overflow-auto whitespace-pre-wrap text-[15px] leading-7 text-ink">
              {diagnosticText}
            </div>
          </div>
        </section>

        <section className="bg-paper p-4">
          <p className="rule-label">Topline interpretation</p>
          <p className="mt-2 text-sm leading-6 text-ink-soft">{result?.summary}</p>
        </section>

        <section className="bg-paper px-4 py-3">
          <div className="flex items-end justify-between border-b border-rule pb-2">
            <div>
              <p className="rule-label">Metric register</p>
              <p className="font-mono text-[10px] uppercase text-muted">normalized score bank</p>
            </div>
            <span className="h-5 w-14 border-t-2 border-cobalt" />
          </div>
          <div className="divide-y divide-rule">
            {metricRows.map((metric) => (
              <ScoreRow key={metric.label} {...metric} />
            ))}
          </div>
        </section>

        <section className="bg-paper p-4">
          <div className="mb-3 min-w-0">
            <p className="rule-label">Follow-up utility</p>
            <h3 className="display-title text-xl">Ask about this project</h3>
          </div>
          <div className="mb-3 max-h-36 space-y-2 overflow-auto">
            {!messages.length && (
              <p className="text-sm leading-6 text-muted">
                Questions stay attached to this diagnostic project.
              </p>
            )}
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={`border-l-2 px-3 py-2 text-sm leading-6 ${
                  message.role === "user"
                    ? "ml-8 border-cobalt bg-[rgba(31,94,255,0.08)] text-cobalt-deep"
                    : message.error
                      ? "mr-8 border-warning bg-paper text-warning"
                      : "mr-8 border-teal bg-porcelain text-ink-soft"
                }`}
              >
                {normalizeDiagnosticText(message.text)}
              </div>
            ))}
          </div>
          <form className="grid grid-cols-[minmax(0,1fr)_auto] gap-2" onSubmit={submit}>
            <textarea
              className="min-h-11 resize-none border border-rule bg-porcelain px-3 py-2 text-sm text-ink outline-none transition focus:border-cobalt"
              placeholder="Ask a targeted follow-up..."
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />
            <button
              className="grid h-11 w-11 place-items-center bg-cobalt text-porcelain transition hover:bg-cobalt-deep disabled:bg-rule-strong"
              disabled={busy || !question.trim()}
              type="submit"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </section>
      </div>
    </aside>
  );
}
