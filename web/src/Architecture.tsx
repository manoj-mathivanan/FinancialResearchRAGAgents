import { ArrowDown, ArrowDownRight, ArrowDownLeft, ArrowUpRight } from "lucide-react";

export function Architecture() {
  return (
    <section className="answer-card architecture" id="architecture" aria-labelledby="architecture-title">
      <h2 id="architecture-title">How FinDoc works</h2>
      <p className="architecture-intro">Three AI agents collaborate on a Research Team question. LangGraph gives each agent an assignment and passes its findings to the answer step.</p>

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
            <span>Caddy is the web server that handles HTTPS and forwards requests to FastAPI. FastAPI is the Python web framework that serves the UI, validates questions, and starts LangGraph.</span>
          </div>
          <ArrowDown className="architecture-arrow" aria-hidden="true" />
          <div className="architecture-node architecture-agent">
            <strong>Research supervisor agent</strong>
            <span><b>LLM:</b> Chooses the reporting quarter and delegates to one or both specialists.</span>
          </div>
          <div className="architecture-branches" aria-hidden="true">
            <ArrowDownLeft /><ArrowDownRight />
          </div>
          <div className="architecture-specialists">
            <div className="architecture-node architecture-agent">
              <strong>Financial investigator agent</strong>
              <span><b>LLM:</b> Chooses which filing figures to look up or compare.</span>
              <span><b>Python tool:</b> Reads the filing snapshot, computes the change, and returns the source for each input.</span>
            </div>
            <div className="architecture-node architecture-agent">
              <strong>Management investigator agent</strong>
              <span><b>LLM:</b> Decides whether a more focused follow-up search could fill an evidence gap.</span>
              <span><b>Retrieval tool:</b> Encodes the query with BGE and uses pgvector to find matching transcript passages.</span>
            </div>
          </div>
          <div className="architecture-branches" aria-hidden="true">
            <ArrowDownRight /><ArrowDownLeft />
          </div>
          <div className="architecture-node">
            <strong>Answer and citations</strong>
            <span><b>LLM:</b> Combines the agents’ findings into claims and selects citations from the evidence provided.</span>
            <span><b>Python:</b> Checks citation labels and attaches the corresponding filing and transcript links.</span>
          </div>
        </div>
        <aside className="architecture-provider" aria-label="External model provider">
          <ArrowUpRight aria-hidden="true" />
          <div>
            <strong>Live LLM provider · Groq</strong>
            <p>The agents share GPT-OSS 20B. Their instructions, tools, and assignments define their separate roles. The specialists can run in parallel when both are needed.</p>
            <strong>Model-serving experiment · Modal</strong>
            <p>Modal hosts a separate GPU endpoint for the same GPT-OSS model. vLLM loads the public weights from Hugging Face and exposes a chat API. The public demo uses Groq.</p>
          </div>
        </aside>
      </div>
      <details className="architecture-search">
        <summary>How BGE embeddings find transcript evidence</summary>
        <p>FastEmbed is the Python library that runs the BGE Small English embedding model on the VPS. BGE turns each transcript passage or search question into a vector of 384 numbers. Related wording can produce similar vectors. This step uses an embedding model and makes no LLM call.</p>
        <p>We store passage vectors once in PostgreSQL alongside the text and PDF page links. For each search, FastEmbed creates a question vector and pgvector finds the closest passages within the selected quarter. The answer model reads the retrieved text.</p>
      </details>
      <p className="architecture-baseline"><strong>Quick research</strong> uses an LLM router to choose the calculator, transcript search, or both. <strong>The quarterly brief</strong> uses reviewed snapshots and Python calculations without an LLM call.</p>
    </section>
  );
}
