import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownRight, ArrowRight, ArrowUpRight, BookOpen, Calculator, FileText,
  Layers3, Search, Workflow,
} from "lucide-react";
import "./style.css";

type FilingInput = {
  period_end: string;
  value: string;
  unit?: string;
  source: { url: string; row?: string; section?: string };
};
type Citation =
  | { type: "filing_calculation"; inputs: { prior: FilingInput; current: FilingInput } }
  | { type: "reported_fact"; input: FilingInput }
  | { type?: undefined; source_url: string; pdf_page: number; transcript_page: number; period_end: string };

type SearchStep = { query: string; pdf_pages: number[] };
type Brief = {
  metrics: { metric: string; prior: FilingInput; current: FilingInput; percent_change: string }[];
  management: { text: string; url: string };
  assessment: string;
  assessment_basis: string;
  gap: string;
};
type Answer = {
  status: "answered" | "partial" | "insufficient_evidence";
  claims: { text: string; source_ids: string[] }[];
  sources: Record<string, Citation>;
  gaps: string[];
  route?: { period_end?: string | null; metric?: string | null; transcript_query?: string | null };
  assignment?: { period_end?: string | null; financial_task?: string | null; management_task?: string | null };
  financial_tools?: { tool: string; metric: string; gap?: string }[];
  transcript_searches?: SearchStep[];
};

const examples = [
  { icon: Calculator, label: "Compare revenue", question: "How much did Infosys revenue grow year over year in the March 2026 quarter?" },
  { icon: FileText, label: "Read management commentary", question: "How did the labor-code change affect Infosys’s operating margin in the December 2025 quarter?" },
  { icon: Layers3, label: "Combine both sources", question: "How did Infosys revenue and profit attributable to owners change year over year in the December 2025 quarter, and how did management explain the labor-code impact on margin?" },
];

function formatQuarter(date: string) {
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(date + "T00:00:00Z"));
}

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

function QuarterlyBrief() {
  const [brief, setBrief] = useState<Brief>();
  const [failed, setFailed] = useState(false);

  async function load() {
    if (brief) return;
    setFailed(false);
    try {
      const response = await fetch("/api/brief");
      if (!response.ok) throw new Error("Brief unavailable");
      setBrief(await response.json());
    } catch {
      setFailed(true);
    }
  }

  const crore = new Intl.NumberFormat("en-IN");
  return <details className="answer-card quarterly-brief" onToggle={event => { if (event.currentTarget.open) void load(); }}>
    <summary>Infosys quarterly brief · December 2025</summary>
    {failed && <p role="alert">The brief is unavailable. Close and reopen it to retry.</p>}
    {!brief && !failed && <p role="status">Loading the quarterly brief…</p>}
    {brief && <>
      <p><strong>Business outlook · {brief.assessment}</strong> {brief.assessment_basis}</p>
      <div className="brief-metrics">
        {brief.metrics.map(metric => <article key={metric.metric}>
          <h3>{metric.metric === "revenue" ? "Revenue" : "Profit attributable to owners"}</h3>
          <strong>{metric.percent_change}</strong>% quarter over quarter
          <p>{formatQuarter(metric.prior.period_end)} · ₹{crore.format(Number(metric.prior.value))} crore<br />
            {formatQuarter(metric.current.period_end)} · ₹{crore.format(Number(metric.current.value))} crore</p>
          <SourceLink url={metric.prior.source.url} label="September filing" />{" · "}
          <SourceLink url={metric.current.source.url} label="December filing" />
        </article>)}
      </div>
      <h3>Management commentary</h3>
      <p>{brief.management.text} <SourceLink url={brief.management.url} label="Earnings call, PDF page 21" /></p>
      <p className="notice">{brief.gap}</p>
    </>}
  </details>;
}

function FilingRow({ fact }: { fact: FilingInput }) {
  return <li>
    <span className="source-date">{formatQuarter(fact.period_end)} quarter</span>
    {fact.source.row && <span className="muted">{fact.source.row}</span>}
    <SourceLink url={fact.source.url} label="Open filing" />
  </li>;
}

function SourceCard({ label, source }: { label: string; source: Citation }) {
  const isFiling = source.type === "filing_calculation" || source.type === "reported_fact";
  return (
    <article className="source-card" id={`source-${label}`} tabIndex={-1}>
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

function WorkflowDetails({ answer }: { answer: Answer }) {
  const tasks = [
    ["Financial investigator", answer.assignment?.financial_task],
    ["Management investigator", answer.assignment?.management_task],
    ["Financial metric", answer.route?.metric],
    ["Transcript query", answer.route?.transcript_query],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]));
  const tools = answer.financial_tools ?? [];
  const searches = answer.transcript_searches ?? [];
  if (!tasks.length && !tools.length && !searches.length) return null;
  return <details className="trace">
    <summary><Workflow size={17} /> How this answer was researched</summary>
    <dl>{tasks.map(([label, task]) => <div key={label}><dt>{label}</dt><dd>{task}</dd></div>)}</dl>
    {tools.length > 0 && <p className="muted">Financial tools: {tools.map((item) =>
      `${item.tool === "compare_yoy" ? "Year-over-year comparison" : "Reported figure"} (${item.metric})`).join(" · ")}</p>}
    {searches.length > 0 && <ol>{searches.map((step, index) => <li key={index}>
      {step.query} <span className="muted">{step.pdf_pages.length ? `· PDF pages ${step.pdf_pages.join(", ")}` : "· No pages returned"}</span>
    </li>)}</ol>}
  </details>;
}

function App() {
  const [periods, setPeriods] = useState<string[]>([]);
  const [period, setPeriod] = useState("");
  const [mode, setMode] = useState<"quick" | "team">("team");
  const [question, setQuestion] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [answer, setAnswer] = useState<Answer>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/config", { signal: controller.signal })
      .then(async response => { if (response.ok) setPeriods((await response.json()).periods); })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !question.trim()) return;
    const text = question.trim();
    setBusy(true);
    setError("");
    setAnswer(undefined);
    setSubmitted(text);
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, period_end: period || null, mode }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Could not run this question. Please try again.");
      }
      setAnswer(await response.json());
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Research is unavailable. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const sources = Object.entries(answer?.sources ?? {});
  const answerPeriod = answer?.assignment?.period_end ?? answer?.route?.period_end;

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="/" aria-label="FinDoc Research home">
            <span className="brand-mark"><Layers3 size={21} strokeWidth={2.1} /></span>
            FinDoc <span>Research</span>
          </a>
          <span className="top-context"><span className="status-dot" /> Infosys <span className="context-divider">/</span> NSE</span>
        </div>
      </header>
      <main className="shell">
        <section className="intro">
          <h1>Company research</h1>
          <p>Ask about Infosys and trace the answer back to a filing or earnings call.</p>
        </section>
        <div className="layout">
          <section className="workspace" aria-label="Question and answer">
            <form className="ask-card" onSubmit={ask}>
              <div className="controls">
                <fieldset disabled={busy}>
                  <legend>Research mode</legend>
                  <div className="segments">
                    <label><input type="radio" name="mode" checked={mode === "quick"} onChange={() => setMode("quick")} /> <span>Quick research</span></label>
                    <label><input type="radio" name="mode" checked={mode === "team"} onChange={() => setMode("team")} /> <span><Workflow size={15} /> Research team</span></label>
                  </div>
                </fieldset>
                <label className="period-control">Reporting quarter
                  <select value={period} onChange={event => setPeriod(event.target.value)} disabled={busy}>
                    <option value="">Infer from question</option>
                    {periods.map(value => <option key={value} value={value}>{formatQuarter(value)}</option>)}
                  </select>
                </label>
              </div>
              <label className="question-label" htmlFor="question">Research question</label>
              <div className="composer">
                <textarea id="question" value={question} onChange={event => setQuestion(event.target.value)}
                  placeholder="How did Infosys revenue change in the December 2025 quarter?" rows={3} maxLength={1200} disabled={busy} required />
                <div className="composer-footer">
                  <span>{mode === "team" ? "Delegates to specialists when needed" : "Routes directly to research tools"}</span>
                  <button className="ask-button" type="submit" disabled={busy || !question.trim()}>
                    {busy ? "Researching…" : "Ask FinDoc"} <ArrowRight size={16} />
                  </button>
                </div>
              </div>
            </form>
            {!submitted && <div className="examples">
              <h2>Try a question</h2>
              <div className="example-list">{examples.map(({ icon: Icon, label, question: sample }) => (
                <button className="example" key={label} type="button" onClick={() => {
                  setQuestion(sample); setPeriod(""); document.getElementById("question")?.focus();
                }}><Icon size={17} /><span>{label}</span><ArrowDownRight className="example-arrow" size={15} /></button>
              ))}</div>
            </div>}
            <div aria-live="polite" aria-busy={busy}>
              {busy && <section className="answer-card loading"><span className="spinner" /> Finding evidence and drafting an answer…</section>}
              {error && <section className="answer-card error" role="alert"><h2>Couldn’t complete the research</h2><p>{error}</p></section>}
              {answer && <section className="answer-card">
                <div className="answer-heading">
                  <h2>Research answer</h2>
                  {answerPeriod && <span className="muted">{formatQuarter(answerPeriod)}</span>}
                </div>
                <p className="asked">{submitted}</p>
                {answer.status === "insufficient_evidence" && <p className="notice">There isn’t enough evidence to answer this question.</p>}
                {answer.status === "partial" && <p className="notice">The available evidence answers part of the question.</p>}
                {answer.claims.map((claim, index) => <p className="claim" key={index}>
                  {claim.text}{" "}
                  {claim.source_ids.filter(id => id in answer.sources).map(id =>
                    <a className="citation" href={`#source-${id}`} key={id} aria-label={`See source ${id}`}>{id}</a>
                  )}
                </p>)}
                {!!answer.gaps?.length && <div className="gaps"><h3>Evidence gaps</h3><ul>{answer.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul></div>}
                <WorkflowDetails answer={answer} />
              </section>}
            </div>
          </section>
          <aside className="evidence-panel" aria-labelledby="sources-heading">
            <div className="panel-heading"><BookOpen size={18} /><h2 id="sources-heading">Source evidence</h2>{sources.length > 0 && <span className="source-count">{sources.length}</span>}</div>
            {sources.length
              ? <div className="source-list">{sources.map(([label, source]) => <SourceCard label={label} source={source} key={label} />)}</div>
              : <div className="empty-sources"><Search size={23} strokeWidth={1.5} /><p>{answer ? "This answer has no cited sources." : "Cited filings and transcript pages will appear here."}</p></div>}
          </aside>
        </div>
        <QuarterlyBrief />
      </main>
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
