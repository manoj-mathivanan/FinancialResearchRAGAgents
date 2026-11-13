import { ArrowDown, ArrowDownRight, ArrowDownLeft, ArrowUpRight } from "lucide-react";

export function Architecture() {
  return (
    <section className="answer-card architecture" id="architecture" aria-labelledby="architecture-title">
      <h2 id="architecture-title">How FinDoc works</h2>
      <p className="architecture-intro">Follow a Research Team question from the browser to a cited answer.</p>

      <div className="architecture-diagram">
        <div className="architecture-node">
          <strong>React in your browser</strong>
          <span>Sends the question and reporting quarter. Displays claims and source links.</span>
        </div>
        <ArrowDown className="architecture-arrow" aria-hidden="true" />
        <div className="architecture-host">
          <h3>DigitalOcean VPS</h3>
          <div className="architecture-node">
            <strong>Caddy → FastAPI → LangGraph</strong>
            <span>Caddy handles HTTPS. FastAPI serves the UI and starts the research workflow.</span>
          </div>
          <ArrowDown className="architecture-arrow" aria-hidden="true" />
          <div className="architecture-node architecture-agent">
            <strong>Research supervisor</strong>
            <span>Chooses the reporting quarter and delegates to one or both specialists.</span>
          </div>
          <div className="architecture-branches" aria-hidden="true">
            <ArrowDownLeft /><ArrowDownRight />
          </div>
          <div className="architecture-specialists">
            <div className="architecture-node architecture-agent">
              <strong>Financial investigator</strong>
              <span>Uses the Python calculator to read reported figures and compute changes from filing snapshots.</span>
            </div>
            <div className="architecture-node architecture-agent">
              <strong>Management investigator</strong>
              <span>Uses local BGE embeddings and PostgreSQL with pgvector to search transcripts. It can refine its search based on the results.</span>
            </div>
          </div>
          <div className="architecture-branches" aria-hidden="true">
            <ArrowDownRight /><ArrowDownLeft />
          </div>
          <div className="architecture-node">
            <strong>Answer and citations</strong>
            <span>Combines the findings. Python resolves the model’s citation labels to filing and transcript links before FastAPI returns the answer.</span>
          </div>
        </div>
        <aside className="architecture-provider" aria-label="External model provider">
          <ArrowUpRight aria-hidden="true" />
          <div>
            <strong>Groq · GPT-OSS 20B</strong>
            <p>LangGraph calls Groq for routing, specialist decisions, and answer generation. FastEmbed runs BGE on the VPS for vector search.</p>
          </div>
        </aside>
      </div>
      <p className="architecture-baseline"><strong>Quick research</strong> uses a single router to call the calculator, transcript search, or both. <strong>The quarterly brief</strong> uses reviewed snapshots and deterministic calculations.</p>
    </section>
  );
}
