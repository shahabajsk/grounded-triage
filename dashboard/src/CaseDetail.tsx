import type { CaseRow } from "./types";

const CITE = /\[((?:txn|cust|merchant|delivery|dispute):[A-Za-z0-9-]+)\]/g;

/** Render a resolution note with each citation as a chip, so a reviewer sees what backs every sentence. */
function Note({ text }: { text: string }) {
  return (
    <div className="note">
      {text.split("\n").map((line, i) => {
        const parts: (string | JSX.Element)[] = [];
        let last = 0;
        for (const m of line.matchAll(CITE)) {
          parts.push(line.slice(last, m.index));
          parts.push(<span key={m.index} className="cite">{m[1]}</span>);
          last = (m.index ?? 0) + m[0].length;
        }
        parts.push(line.slice(last));
        return <p key={i}>{parts}</p>;
      })}
    </div>
  );
}

export function CaseDetail({ row, verdictLabel }: { row: CaseRow; verdictLabel: string }) {
  return (
    <article className="detail" aria-live="polite">
      <header>
        <h2>{row.id}</h2>
        <span className={`verdict v-${row.verdict}`}>{verdictLabel}</span>
      </header>
      <blockquote>{row.complaint}</blockquote>

      <dl className="facts">
        <div><dt>Expected</dt><dd>{row.expected_action.replace("_", " ")} · {row.expected_category.replace("_", " ")}</dd></div>
        <div><dt>Agent</dt><dd>{row.action.replace("_", " ")}{row.category ? ` · ${row.category.replace("_", " ")}` : ""}</dd></div>
        {row.confidence !== null && <div><dt>Confidence</dt><dd>{row.confidence.toFixed(2)}</dd></div>}
        <div><dt>Drafts</dt><dd>{row.draft_attempts} written, {row.verifier_rejections} rejected</dd></div>
      </dl>

      <h3>State trace</h3>
      <ol className="trace">
        {row.trace.map((s, i) => (
          <li key={i} className={`st-${s.state}${s.note.startsWith("rejected") ? " rejected" : ""}`}>
            <span className="st">{s.state.replace("_", " ")}</span>
            <span className="sn">{s.note}</span>
          </li>
        ))}
      </ol>

      <h3>Resolution note</h3>
      {row.draft ? (
        <Note text={row.draft} />
      ) : (
        <p className="muted">No note shipped. {row.escalation_reason ? `Sent to an analyst: ${row.escalation_reason}.` : ""}</p>
      )}
    </article>
  );
}
