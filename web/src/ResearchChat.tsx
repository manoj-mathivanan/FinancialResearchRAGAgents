import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { ArrowDownRight, ArrowRight, Calculator, FileText, Layers3 } from "lucide-react";
import { EvidencePanel } from "./EvidencePanel";
import { ResearchAnswer } from "./ResearchAnswer";
import { ResearchMode } from "./ResearchMode";
import type { Mode } from "./ResearchMode";
import { answerQuarter, formatQuarter } from "./researchTypes";
import type { Answer } from "./researchTypes";

const examples = [
  { icon: Calculator, label: "Compare revenue", question: "How much did Infosys revenue grow year over year in the March 2026 quarter?" },
  { icon: FileText, label: "Read management commentary", question: "How did the labor-code change affect Infosys’s operating margin in the December 2025 quarter?" },
  { icon: Layers3, label: "Combine both sources", question: "How did Infosys revenue and profit attributable to owners change year over year in the December 2025 quarter, and how did management explain the labor-code impact on margin?" },
];

export function ResearchChat() {
  const [periods, setPeriods] = useState<string[]>([]);
  const [period, setPeriod] = useState("");
  const [mode, setMode] = useState<Mode>("team");
  const [symbol, setSymbol] = useState("INFY");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<{ question: string; answer: Answer }[]>([]);
  const [sourceTurn, setSourceTurn] = useState(0);
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
    // Keep the on-screen thread in React. Send only recent answered turns as context.
    const history = turns.filter(turn => turn.answer.claims.length).slice(-3).map(turn => ({
      question: turn.question,
      answer: turn.answer.claims.map(claim => claim.text).join(" ").slice(0, 1200),
      period_end: answerQuarter(turn.answer),
    }));
    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, symbol, period_end: period || null, mode, history }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(typeof data?.detail === "string" ? data.detail : "Could not run this question. Please try again.");
      }
      const answer: Answer = await response.json();
      setTurns([...turns, { question: text, answer }]);
      setSourceTurn(turns.length);
      setQuestion("");
      requestAnimationFrame(() => document.getElementById("question")?.focus());
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Research is unavailable. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function showCitation(turn: number, id: string) {
    // Source labels restart at S1 on each answer, so include the turn in the target ID.
    setSourceTurn(turn);
    requestAnimationFrame(() => document.getElementById(`source-${turn}-${id}`)?.focus());
  }

  return (
    <div className="layout">
      <section className="workspace" aria-label="Question and answer">
        <section className="examples" aria-labelledby="examples-heading">
          <h2 id="examples-heading">Try a question</h2>
          <div className="example-list">{examples.map(({ icon: Icon, label, question: sample }) => (
            <button className="example" key={label} type="button" disabled={busy} onClick={() => {
              setQuestion(sample); setPeriod(""); document.getElementById("question")?.focus();
            }}><Icon size={17} /><span>{label}</span><ArrowDownRight className="example-arrow" size={15} /></button>
          ))}</div>
        </section>
        <form className="ask-card" onSubmit={ask}>
          <div className="chat-heading">
            <p className="muted">Follow-ups use up to three recent answers. This chat clears when you reload.</p>
            {turns.length > 0 && <button className="new-chat" type="button" disabled={busy} onClick={() => {
              setTurns([]); setSourceTurn(0); setPeriod(""); setQuestion(""); setError("");
            }}>New chat</button>}
          </div>
          <div className="controls">
            <label className="period-control">Stock
              <select value={symbol} onChange={event => setSymbol(event.target.value)} disabled={busy}>
                <option value="INFY">Infosys (INFY)</option>
              </select>
            </label>
            <label className="period-control">Reporting quarter
              <select value={period} onChange={event => setPeriod(event.target.value)} disabled={busy}>
                <option value="">Infer from chat</option>
                {periods.map(value => <option key={value} value={value}>{formatQuarter(value)}</option>)}
              </select>
            </label>
          </div>
          <div className="question-mode"><ResearchMode name="mode" label="Research mode" mode={mode} onChange={setMode} disabled={busy} /></div>
          <div aria-live="polite" aria-busy={busy}>
            {turns.map(({ question: asked, answer }, turn) => (
              <div className="chat-turn" key={turn}>
                <p className="user-message"><strong>You</strong><span>{asked}</span></p>
                <ResearchAnswer answer={answer} turn={turn} onCitation={showCitation} />
              </div>
            ))}
            {busy && <p className="loading"><span className="spinner" /> Finding evidence and drafting an answer…</p>}
            {error && <p className="notice error" role="alert">{error}</p>}
          </div>
          <label className="question-label" htmlFor="question">{turns.length ? "Follow-up question" : "Research question"}</label>
          <div className="composer">
            <textarea id="question" value={question} onChange={event => setQuestion(event.target.value)}
              placeholder={turns.length ? "What about profit for the same quarter?" : "How did Infosys revenue change in the December 2025 quarter?"} rows={3} maxLength={1200} disabled={busy} required />
            <div className="composer-footer">
              <button className="ask-button" type="submit" disabled={busy || !question.trim()}>
                {busy ? "Researching…" : "Ask FinDoc"} <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </form>
      </section>
      <EvidencePanel answer={turns[sourceTurn]?.answer} sourceTurn={sourceTurn} hasTurns={turns.length > 0} />
    </div>
  );
}
