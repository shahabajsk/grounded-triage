import { useEffect, useMemo, useState } from "react";
import type { CaseRow, Report, Run, Verdict } from "./types";
import { CaseDetail } from "./CaseDetail";

const VERDICT_LABEL: Record<Verdict, string> = {
  correct: "Correct",
  unsafe: "Wrong auto-decision",
  over_escalation: "Escalated, didn't need to",
};

type Filter = "all" | Verdict | "escalated";

function pct(n: number) {
  return `${Math.round(n * 100)}%`;
}

export default function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runIdx, setRunIdx] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetch("./eval.json")
      .then((r) => {
        if (!r.ok) throw new Error(`eval.json returned ${r.status}`);
        return r.json();
      })
      .then((data: Report) => {
        setReport(data);
        setRunIdx(data.runs.length - 1);
      })
      .catch((e: Error) =>
        setError(`${e.message}. Run "python -m grounded_triage.eval" and copy reports/eval.json into dashboard/public/.`),
      );
  }, []);

  const run: Run | undefined = report?.runs[runIdx];

  const rows = useMemo(() => {
    if (!run) return [];
    return run.rows
      .filter((r) => {
        if (filter === "all") return true;
        if (filter === "escalated") return r.action === "escalate";
        return r.verdict === filter;
      })
      .sort((a, b) => a.id.localeCompare(b.id));
  }, [run, filter]);

  const current: CaseRow | undefined = run?.rows.find((r) => r.id === selected) ?? rows[0];

  if (error) return <main className="shell"><p className="error">{error}</p></main>;
  if (!report || !run) return <main className="shell"><p className="muted">Loading eval report…</p></main>;

  const injected = run.fabrications_injected ?? 0;

  return (
    <main className="shell">
      <header className="masthead">
        <h1>Dispute triage console</h1>
        <p className="lede">
          {run.cases} synthetic card disputes, run through a state-machine agent. Every resolution note is checked
          against the ledger before it can leave the system.
        </p>
        <label className="run-picker">
          <span>Model run</span>
          <select value={runIdx} onChange={(e) => { setRunIdx(Number(e.target.value)); setSelected(null); }}>
            {report.runs.map((r, i) => (
              <option key={r.model} value={i}>{r.model}</option>
            ))}
          </select>
        </label>
      </header>

      <section className="ledger-strip" aria-label="Fabrication funnel">
        <div className="funnel">
          <div className="funnel-step">
            <span className="funnel-num">{injected}</span>
            <span className="funnel-label">fabrications injected into drafts</span>
          </div>
          <div className="funnel-step">
            <span className="funnel-num">{run.verifier_rejections}</span>
            <span className="funnel-label">drafts rejected by the verifier</span>
          </div>
          <div className={`funnel-step ${run.fabricated_notes_shipped === 0 ? "is-zero" : "is-bad"}`}>
            <span className="funnel-num">{run.fabricated_notes_shipped}</span>
            <span className="funnel-label">unverified notes shipped</span>
          </div>
        </div>
        <dl className="kpis">
          <div><dt>Right action</dt><dd>{pct(run.action_accuracy)}</dd></div>
          <div><dt>Closed without a human</dt><dd>{pct(run.automation_rate)}</dd></div>
          <div><dt>Wrong auto-decisions</dt><dd className={run.unsafe_auto_decisions ? "bad" : ""}>{run.unsafe_auto_decisions}</dd></div>
          <div><dt>Needless escalations</dt><dd>{run.over_escalations}</dd></div>
        </dl>
      </section>

      <section className="workspace">
        <div className="queue">
          <div className="filters" role="tablist" aria-label="Filter cases">
            {(["all", "unsafe", "over_escalation", "escalated", "correct"] as Filter[]).map((f) => (
              <button
                key={f}
                role="tab"
                aria-selected={filter === f}
                className={filter === f ? "on" : ""}
                onClick={() => { setFilter(f); setSelected(null); }}
              >
                {f === "all" ? "All" : f === "escalated" ? "Escalated" : VERDICT_LABEL[f as Verdict]}
              </button>
            ))}
          </div>
          <table>
            <thead>
              <tr><th>Case</th><th>Complaint</th><th>Action</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className={`${current?.id === r.id ? "sel" : ""} v-${r.verdict}`}
                  onClick={() => setSelected(r.id)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && setSelected(r.id)}
                >
                  <td className="id">{r.id}</td>
                  <td>{r.complaint}</td>
                  <td><span className={`tag a-${r.action}`}>{r.action.replace("_", " ")}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="muted pad">No cases in this view.</p>}
        </div>

        {current && <CaseDetail row={current} verdictLabel={VERDICT_LABEL[current.verdict]} />}
      </section>
    </main>
  );
}
