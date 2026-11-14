import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { ResearchMode } from "./ResearchMode";
import type { Mode } from "./ResearchMode";

export function Architecture() {
  const [mode, setMode] = useState<Mode>("team");
  const team = mode === "team";

  return (
    <section className="answer-card architecture" id="architecture" aria-labelledby="architecture-title">
      <h2 id="architecture-title">How FinDoc works</h2>
      <p className="architecture-intro">
        React sends your question to the DigitalOcean VPS. Caddy handles HTTPS, FastAPI validates the request, and LangGraph runs the selected workflow.
      </p>
      <ResearchMode name="architecture-mode" label="Workflow to explore" mode={mode} onChange={setMode} />
      <p id="architecture-scroll-hint" className="architecture-scroll-hint">Scroll right to follow the workflow.</p>

      <div className="architecture-scroll" role="region" aria-label="Left-to-right research workflow"
        aria-describedby="architecture-scroll-hint" tabIndex={0}>
        <div className="architecture-diagram">
          <div className="architecture-node">
            <strong>Question</strong>
            <span>React sends the stock, quarter, question, and mode to FastAPI.</span>
          </div>
          <ArrowRight className="architecture-arrow" aria-hidden="true" />
          <div className="architecture-node architecture-agent">
            <strong>{team ? "Research supervisor agent" : "Quick research router"}</strong>
            <span><b>LLM:</b> {team ? "Assigns work to one or both specialists." : "Selects the calculator, transcript search, or both."}</span>
          </div>
          <ArrowRight className="architecture-arrow" aria-hidden="true" />
          <div className="architecture-specialists" aria-label="One or both evidence paths">
            <div className="architecture-node">
              <strong>{team ? "Financial investigator agent" : "Financial calculator"}</strong>
              {team && <span><b>LLM:</b> Chooses the figures and comparisons to request.</span>}
              <span><b>Python tool:</b> Reads filing snapshots, computes changes, and returns citation details.</span>
            </div>
            <div className="architecture-node">
              <strong>{team ? "Management investigator agent" : "Transcript search"}</strong>
              {team && <span><b>LLM:</b> Can request up to two follow-up searches when evidence is missing.</span>}
              <span><b>Retrieval tool:</b> Uses BGE and pgvector to fetch earnings-call evidence for RAG.</span>
            </div>
          </div>
          <ArrowRight className="architecture-arrow" aria-hidden="true" />
          <div className="architecture-node">
            <strong>Cited answer</strong>
            <span><b>LLM:</b> Writes claims from the supplied evidence.</span>
            <span><b>Python:</b> Resolves citation labels to source links and returns the answer to React.</span>
          </div>
        </div>
      </div>

      <p className="architecture-provider"><strong>Groq hosts GPT-OSS 20B.</strong> The LLM steps above call Groq. The calculator, vector search, and citation checks run as code on the VPS. BGE is a separate embedding model that runs locally through FastEmbed.</p>

      <div className="architecture-rag">
        <h3>How transcript RAG was built and where it runs</h3>
        <p>Retrieval-augmented generation (RAG) gives the answer model relevant source passages. Both modes use it when they need transcript evidence.</p>
        <dl>
          <div><dt>Extract and split</dt><dd>Python uses Poppler to extract the NSE earnings-call PDFs page by page. It splits the call text into passages of up to 140 words with a 30-word overlap, keeping each passage on one PDF page.</dd></div>
          <div><dt>Embed and store</dt><dd>FastEmbed runs BGE Small English to produce a 384-number vector per passage. PostgreSQL 17 with pgvector runs on the DigitalOcean VPS and stores each vector alongside the text, quarter, and PDF link.</dd></div>
          <div><dt>Retrieve and cite</dt><dd>FastEmbed embeds the search query with the same model. pgvector ranks passages by similarity within the selected quarter. FinDoc sends their readable text to Groq and uses the saved page links for citations.</dd></div>
        </dl>
        <p className="architecture-baseline">Financial calculations read reviewed filing snapshots directly. The quarterly brief uses those snapshots and Python calculations without an LLM call.</p>
      </div>
    </section>
  );
}
