import { ArrowUpRight, BookOpen, Search } from "lucide-react";
import { formatQuarter } from "./researchTypes";
import type { Answer, Citation, FilingInput } from "./researchTypes";

function externalUrl(value: string) {
  try {
    const url = new URL(value);
    if (url.protocol === "https:" && !url.username && !url.password) return url.href;
  } catch {
    return undefined;
  }
  return undefined;
}

function SourceLink({ url, label }: { url: string; label: string }) {
  const href = externalUrl(url);
  return href
    ? <a className="source-link" href={href} target="_blank" rel="noopener noreferrer">{label} <ArrowUpRight size={14} /></a>
    : <span className="muted">Source link unavailable</span>;
}

// A calculation cites both filing rows; transcript links preserve the PDF page.
function FilingRow({ fact }: { fact: FilingInput }) {
  return <li>
    <span className="source-date">{formatQuarter(fact.period_end)} quarter</span>
    {fact.source.row && <span className="muted">{fact.source.row}</span>}
    <SourceLink url={fact.source.url} label="Open filing" />
  </li>;
}

function SourceCard({ label, source, turn }: { label: string; source: Citation; turn: number }) {
  const isFiling = source.type === "filing_calculation" || source.type === "reported_fact";
  return (
    <article className="source-card" id={`source-${turn}-${label}`} tabIndex={-1}>
      <div className="source-heading"><span className="citation">{label}</span><strong>{isFiling ? "Financial filing" : "Earnings call"}</strong></div>
      {source.type === "filing_calculation"
        ? <ul className="filing-list"><FilingRow fact={source.inputs.prior} /><FilingRow fact={source.inputs.current} /></ul>
        : source.type === "reported_fact"
          ? <ul className="filing-list"><FilingRow fact={source.input} /></ul>
          : <div className="transcript-link">
              <span className="muted">{formatQuarter(source.period_end)} quarter · transcript page {source.transcript_page}</span>
              <SourceLink url={source.source_url} label={`Open PDF page ${source.pdf_page}`} />
            </div>
      }
    </article>
  );
}

export function EvidencePanel({ answer, sourceTurn, hasTurns }: {
  answer?: Answer;
  sourceTurn: number;
  hasTurns: boolean;
}) {
  const sources = Object.entries(answer?.sources ?? {});
  return (
    <aside className="evidence-panel" aria-labelledby="sources-heading">
      <div className="panel-heading"><BookOpen size={18} /><h2 id="sources-heading">Source evidence</h2>{sources.length > 0 && <span className="source-count">{sources.length}</span>}</div>
      {sources.length
        ? <div className="source-list">{sources.map(([label, source]) => <SourceCard label={label} source={source} turn={sourceTurn} key={label} />)}</div>
        : <div className="empty-sources"><Search size={23} strokeWidth={1.5} /><p>{hasTurns ? "This answer has no cited sources." : "Cited filings and transcript pages will appear here."}</p></div>}
    </aside>
  );
}
