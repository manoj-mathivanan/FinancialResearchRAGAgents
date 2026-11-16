export function ProductionReadiness() {
  return (
    <section className="production-readiness" aria-labelledby="production-readiness-title">
      <h3 id="production-readiness-title">Before a production rollout</h3>
      <p>
        FinDoc is a public research demo. It already validates requests and citation IDs, bounds agent
        tool calls, and uses a read-only database role. The work below would prepare it for sustained use.
      </p>
      <dl>
        <div>
          <dt>Observability and monitoring</dt>
          <dd>Trace each request across routing, tool calls, retrieval, and generation. Monitor latency, errors, and model spend. Alert on service degradation.</dd>
        </div>
        <div>
          <dt>API gateway and authentication</dt>
          <dd>Build on Caddy’s HTTPS entry point with identity, access controls, and per-user or per-client quotas.</dd>
        </div>
        <div>
          <dt>Model gateway</dt>
          <dd>Centralize provider routing, timeouts, and spend limits. Test fallback models against each role’s structured response schema.</dd>
        </div>
        <div>
          <dt>Guardrails and human review</dt>
          <dd>Test how agents handle instructions embedded in sources. Route ambiguous or unsupported findings to a reviewer before publication.</dd>
        </div>
        <div>
          <dt>Validation and evaluation</dt>
          <dd>Check figures, units, reporting periods, and whether sources support each claim. Use a held-out question set to test tool selection, retrieval, citations, and when to say evidence is missing.</dd>
        </div>
        <div>
          <dt>Research and context tuning</dt>
          <dd>Improve specialist assignments and search queries. Test combining keyword and vector search, reranking passages, and selecting which chat history and evidence each prompt needs.</dd>
        </div>
        <div>
          <dt>LLM fine-tuning</dt>
          <dd>Benchmark prompt changes first. If a role still makes the same mistakes, test fine-tuning on curated examples and measure the change on separate questions.</dd>
        </div>
        <div>
          <dt>Capacity and autoscaling</dt>
          <dd>Load-test concurrent research requests against database and provider limits, then size workers and scale within those limits.</dd>
        </div>
        <div>
          <dt>Semantic cache</dt>
          <dd>Start with standalone questions in the same company, quarter, and research mode. Invalidate cached answers when source data, prompts, or models change.</dd>
        </div>
      </dl>
    </section>
  );
}
