import { Workflow } from "lucide-react";
import { answerQuarter, formatQuarter } from "./researchTypes";
import type { Answer } from "./researchTypes";

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

export function ResearchAnswer({ answer, turn, onCitation }: {
  answer: Answer;
  turn: number;
  onCitation: (turn: number, id: string) => void;
}) {
  const answerPeriod = answerQuarter(answer);
  return (
    <section className="chat-answer">
      <div className="answer-heading">
        <h2>Research answer</h2>
        {answerPeriod && <span className="muted">{formatQuarter(answerPeriod)}</span>}
      </div>
      {answer.status === "insufficient_evidence" && <p className="notice">There isn’t enough evidence to answer this question.</p>}
      {answer.status === "partial" && <p className="notice">The available evidence answers part of the question.</p>}
      {answer.claims.map((claim, index) => <p className="claim" key={index}>
        {claim.text}{" "}
        {claim.source_ids.filter(id => id in answer.sources).map(id =>
          <a className="citation" href={`#source-${turn}-${id}`} key={id} aria-label={`See source ${id}`} onClick={event => {
            event.preventDefault();
            onCitation(turn, id);
          }}>{id}</a>
        )}
      </p>)}
      {!!answer.gaps?.length && <div className="gaps"><h3>Evidence gaps</h3><ul>{answer.gaps.map(gap => <li key={gap}>{gap}</li>)}</ul></div>}
      <WorkflowDetails answer={answer} />
    </section>
  );
}
