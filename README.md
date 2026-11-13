# FinDocRAGAgents

The first runnable slice compares two Infosys quarters using reported consolidated Ind AS figures and returns the inputs, formula, and source coordinates. Run it from the project folder with Python 3.10 or newer.

```powershell
python -m findoc.compare data/infosys-q4-fy26.json revenue 2026-03-31
python -m findoc.compare data/infosys-q4-fy26.json owners-profit 2026-03-31
python -m unittest discover -s tests -v
```

## Step 1. Trace a number back to the filing

1. Open the detailed consolidated audited statement and find the **Revenue from operations** row. Match the March 2026 and March 2025 **quarter** columns. The year column can have the same end date, so record both dates. [Infosys filing on EDGAR](https://www.sec.gov/Archives/edgar/data/1067491/000106749126000018/exv99w06.htm)
2. Inspect the four manually transcribed values in [the snapshot](data/infosys-q4-fy26.json). Consolidated figures cover Infosys and its subsidiaries. A crore is ten million. Profit attributable to owners excludes the portion attributable to non-controlling interests.
3. Run the comparison. Revenue went from INR 40,925 crore to INR 46,402 crore. The difference is INR 5,477 crore. Divide the difference by the earlier value to get 13.38% growth. Decimal arithmetic and explicit rounding make that result reproducible.
4. Inspect the JSON result. Each input retains its exact period, filing URL, section, and row. Later, agents can call the comparison function and cite its inputs.
5. Run the tests. One fixture adds a full-year number with the same end date and verifies that the calculation still selects the quarter. Other fixtures check missing and duplicate facts and nonpositive percentage baselines.

The manual reference uses prior-year comparatives from the FY2026 statement. Keep it separate from generated data so it can catch extraction errors.

## Step 2. Extract and validate facts from NSE filings

Download local copies of the two consolidated Ind AS filings, then run the parser. Keeping the download separate lets you repeat extraction against the same files. The output command expects a new filename so that reruns preserve previous snapshots.

```powershell
$fy25 = Join-Path $env:TEMP 'findoc-infy-nse25.html'
$fy26 = Join-Path $env:TEMP 'findoc-infy-nse.html'
$out = Join-Path $env:TEMP ('findoc-extracted-' + [guid]::NewGuid() + '.json')
Invoke-WebRequest -ErrorAction Stop -Uri 'https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_85350_17042025233634_iXBRL_WEB.html' -OutFile $fy25
Invoke-WebRequest -ErrorAction Stop -Uri 'https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_152465_23042026210154_iXBRL_WEB.html' -OutFile $fy26
python -m findoc.ingest --fy25 $fy25 --fy26 $fy26 --reference data/infosys-q4-fy26.json --output $out
python -m findoc.compare $out revenue 2026-03-31
python -m findoc.compare $out owners-profit 2026-03-31
```

1. **Read the filing as tables.** The structured HTML preserves cell boundaries and metadata. The parser identifies the Infosys filing and the table containing both target metrics. The label “Revenue from operations” also appears in a segment table, so a text match alone is ambiguous.
2. **Match the column.** Select January 1 through March 31 and check that the results are consolidated and audited. The annual column also ends on March 31.
3. **Normalize the unit.** FY2025 reports in INR actuals, so divide by 10,000,000. FY2026 reports in INR lakh, so divide by 100. Both produce INR crore. For example, FY2026 revenue of 46,40,200 lakh becomes 46,402 crore. [FY2025 filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_85350_17042025233634_iXBRL_WEB.html), [FY2026 filing](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_152465_23042026210154_iXBRL_WEB.html)
4. **Keep the evidence.** Each fact carries the raw value, unit, source URL, table/row/cell positions, and SHA-256 of the downloaded file. The hash identifies the exact file used.
5. **Validate before writing.** The command checks all four metric/period/value combinations against the manual reference. The existing comparison then returns 13.38% revenue growth and 20.87% profit growth.

### Extend the check to Q3 FY2026

Reuse the `$fy25` and `$fy26` downloads from above. The December filing puts a three-month quarter next to a nine-month year-to-date total. Both columns end on December 31. Checking for a start date of October 1 distinguishes the quarter from the year-to-date total starting April 1.

```powershell
$q3 = Join-Path $env:TEMP 'findoc-infy-q3-fy26.html'
$out = Join-Path $env:TEMP ('findoc-three-quarters-' + [guid]::NewGuid() + '.json')
Invoke-WebRequest -ErrorAction Stop -Uri 'https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_135037_14012026203832_iXBRL_WEB.html' -OutFile $q3
python -m findoc.ingest --fy25 $fy25 --fy26 $fy26 --q3-fy26 $q3 --reference data/infosys-q4-fy26.json --reference data/infosys-q3-fy26.json --output $out
(Get-Content -Raw $out | ConvertFrom-Json).facts | Format-Table metric, start, end, value
```

Expect six facts across the three quarters. The two December values, revenue of INR 45,479 crore and profit attributable to owners of INR 6,654 crore, were checked against the separately published consolidated audited statement. The parser now keys source configuration by quarter-end date. This keeps December 2025 and March 2025 distinct even though both dates share a calendar year. [Infosys Q3 FY2026 audited results](https://www.infosys.com/investors/reports-filings/quarterly-results/2025-2026/q3/documents/q3-and-9m-fy26-financial-results-auditorsreports.pdf)

The HTML parser covers these three configured Infosys filings and two metrics. The research workflow supplements the extracted coverage with a separate December 2024 reference snapshot checked against the audited result and the following year's comparative column. [Infosys Q3 FY2025 audited results](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q3/documents/q3-and-9m-fy25-financial-results-auditorsreports.pdf)

## Step 3. Search narrative evidence

Use Python with SQLite FTS5 and install Poppler's `pdftotext` on your PATH. Download the exchange filing to a local temporary folder and build an index. The same database can then serve multiple searches.

```powershell
$pdf = Join-Path $env:TEMP 'findoc-infy-q3-nse-transcripts.pdf'
$db = Join-Path $env:TEMP 'findoc-infy-q3-evidence.sqlite3'
Invoke-WebRequest -ErrorAction Stop -Uri 'https://nsearchives.nseindia.com/corporate/Infosys_19012026222220_SEfiling_Earningscalltranscript_19012026.pdf' -OutFile $pdf
python -m findoc.evidence index $pdf $db
python -m findoc.evidence search $db 'labor codes operating margins'
```

1. **Extract one entry per page.** Poppler inserts a page break between pages. The NSE PDF includes a cover letter and press conference before the earnings call. The parser checks the expected layout and indexes the 21 call pages after the roster.
2. **Build a keyword baseline.** SQLite FTS5 indexes the page text and applies stemming so that related forms such as “margin” and “margins” can match. Every query term must match. BM25 ranks the matching pages using term frequency, rarity, and page length. This baseline lets us measure retrieval before adding embeddings.
3. **Read the first result.** The query returns PDF page 21 first. It is printed page 4 of the call. The CFO describes reported operating margin of 18.4% and adjusted margin of 21.2% after excluding the impact of the labor-code change. Operating margin measures operating profit as a share of revenue. [NSE transcript, PDF page 21](https://nsearchives.nseindia.com/corporate/Infosys_19012026222220_SEfiling_Earningscalltranscript_19012026.pdf#page=21)
4. **Try a query with no evidence.** Search for `quantum giraffe` and expect an empty list. A later answer layer can use this to recognize a retrieval miss.

### Add the corresponding FY2025 call

The January 2025 call covers the quarter ended December 31, 2024. Add it to the same database so both calls can be searched. Reindexing replaces only the selected call.

```powershell
$priorPdf = Join-Path $env:TEMP 'findoc-infy-q3-fy25-call.pdf'
Invoke-WebRequest -ErrorAction Stop -Uri 'https://nsearchives.nseindia.com/corporate/Infosys_21012025151633_SEfiling_Earningscalltranscript.pdf' -OutFile $priorPdf
python -m findoc.evidence index $priorPdf $db
python -m findoc.evidence search $db 'operating margins expanded' --period-end 2024-12-31
python -m findoc.evidence search $db 'labor codes operating margins' --period-end 2025-12-31
```

The earlier call has 23 searchable pages. Its first query returns the reported 21.3% operating margin on printed page 5, PDF page 25. The later call has 21 searchable pages. Filter by the quarter end when comparing periods, and identify whether each measure is reported or adjusted. [FY2025 transcript, PDF page 25](https://nsearchives.nseindia.com/corporate/Infosys_21012025151633_SEfiling_Earningscalltranscript.pdf#page=25)

The index returns page citations and short snippets for both transcripts. It serves as our keyword baseline.

## Step 4. Embed the transcripts and compare retrieval

1. **Split each page into passages.** The vector command reuses the PDF extraction above and groups words into passages of up to 140 words, with a 30-word overlap so nearby context can survive a boundary. Each passage stays on one page so the citation stays precise.
2. **Create embeddings locally.** FastEmbed runs the BGE Small English model on the CPU. The first run downloads model files. Subsequent runs can use the local cache. The model turns each passage into 384 numbers and uses the corresponding query encoding when a question arrives. [BGE model card](https://huggingface.co/BAAI/bge-small-en-v1.5)
3. **Store and search the vectors.** LangChain's `PGVectorStore` sets up the PostgreSQL table and handles ranked search through pgvector. PostgreSQL stores the passage, quarter, page, source link, file hash, and vector. We keep the best passage per page for comparison with SQLite's page-level results. Reindexing a quarter uses a single transaction so a failed insert preserves the previous data. [LangChain Postgres integration](https://github.com/langchain-ai/langchain-postgres#vectorstore), [pgvector documentation](https://github.com/pgvector/pgvector)
4. **Compare the same queries.** The evaluation runs four hand-labeled queries through both paths with the same period filter. A hit means the expected page appears in the first three results. This checks the pipeline on two transcripts. A larger held-out set with multiple acceptable pages is needed to evaluate retrieval quality.

Install the vector dependencies in the project environment. Set `FINDOC_DATABASE_URL` to a PostgreSQL database with the pgvector extension available. The indexing role needs permission to create the extension and table, or an administrator can install the extension first. Use the two transcript PDFs and keyword database from Step 3.

If you built the original SQL-based vector index, rerun the indexing command below. The new integration writes to `transcript_vectors` and leaves the original `transcript_passages` table available.

```powershell
uv venv .venv
uv pip install -r requirements-vector.txt
# Set FINDOC_DATABASE_URL in this shell before running the commands.
.\.venv\Scripts\python.exe -m findoc.vector index $priorPdf $pdf
.\.venv\Scripts\python.exe -m findoc.vector search 'How did new employment rules affect profitability?' --period-end 2025-12-31
.\.venv\Scripts\python.exe -m findoc.vector evaluate $db data/retrieval-smoke.json
```

For this implementation check, the Python client connected to a temporary local PGlite PostgreSQL instance with pgvector. The planned application deployment uses a regular PostgreSQL server. [PGlite extensions](https://pglite.dev/extensions/)

The run stored 153 passages. Keyword search found the expected page in the top three for two of the four queries. Vector search found it for all four. The two paraphrases were misses for the current keyword command because it requires every input term. The employment-rules question returned the expected page second with vectors. This is a smoke test against known pages, so the results describe these four queries only.

## Build and learning sequence

The code follows these paths:

| Location | Responsibility |
|---|---|
| [`findoc/tools/transcripts.py`](findoc/tools/transcripts.py) | Shared PDF extraction and source page metadata used by both retrieval methods |
| [`findoc/baseline/`](findoc/baseline) | SQLite keyword search and evaluation against expected pages |
| [`findoc/vector.py`](findoc/vector.py) | Embedding and vector retrieval for the answer workflow |
| [`findoc/answer.py`](findoc/answer.py) | Passes retrieved evidence to the answer model and resolves its citations |

The original `findoc.evidence` command still opens the keyword baseline. Running vector indexing or search only loads the shared transcript reader. The `evaluate` subcommand calls both search methods. The financial calculator remains in [`findoc/compare.py`](findoc/compare.py) for the future answer workflow to call when it needs arithmetic.

| Step | Build | What we check before moving on |
|---|---|---|
| 1 | Cited Infosys comparison | Values reconcile to the filing and period matching handles an annual column |
| 2 | Source inventory and automated ingestion for one company | First slice verified on three Infosys filings, including a quarter with a nine-month comparative column |
| 3 | Narrative retrieval and cited single-agent Q&A | Compare keyword and vector retrieval on the same pages, then evaluate generated answers and citations |
| 4 | Expand across the five companies and eight quarters | Check data coverage, revised comparatives, and consistent scope/units |
| 5 | Add specialists and independent verification | Compare against the single-agent baseline on the same questions and similar budgets |
| 6 | Integrate real market data and benchmarks | Verify data-use rights, trading dates, corporate actions, and return conventions |
| 7 | Deploy the public demo | Verify citation navigation, live Q&A, briefs, chart accuracy, and recovery |

At each step, start with a worked example, implement it, measure the result, and use the observed failures to choose the next improvement. [Full project plan](PROJECT_PLAN.md)

## Step 5. Generate a cited answer

1. **Retrieve.** Reuse the indexed PostgreSQL database to get up to three pages from the requested quarter.
2. **Add the passages to the prompt.** Python gives each passage a short label, such as `S1`, and includes its text in the prompt.
3. **Generate and resolve citations.** The model returns structured claims with source labels or reports insufficient evidence. Python checks that each label came from the retrieved set and attaches the original page URL. This catches invented labels. A separate evaluation must check whether the cited text actually supports each claim. [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

The default answer model is `gpt-5.6-terra`. Use `--model` to select another model available to your API project that supports Structured Outputs. This command sends the question and retrieved text to the OpenAI API. Set `OPENAI_API_KEY` in your environment or the ignored `.env` file at the project root. Existing environment variables take precedence. [Model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [API key setup](https://developers.openai.com/api/docs/quickstart#create-and-export-an-api-key)

```powershell
uv pip install -r requirements-answer.txt
# Configure FINDOC_DATABASE_URL and OPENAI_API_KEY in your environment.
.\.venv\Scripts\python.exe -m findoc.answer 'How did new employment rules affect profitability?' --period-end 2025-12-31
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests use a simulated model response and do not need an API key. The transcript answer command covers earnings-call evidence for one quarter.

## Step 6. Explain a verified calculation

Use the same answer command with a snapshot and metric. The calculation path reads the JSON file directly and needs no vector database.

```powershell
.\.venv\Scripts\python.exe -m findoc.answer 'How much did Infosys revenue grow year over year?' --period-end 2026-03-31 --snapshot data/infosys-q4-fy26.json --metric revenue
```

Python selects the two reported quarter values, calculates the change using decimal arithmetic, and supplies the result to the model. A calculation citation attaches the two filing references, including the row and reporting period for each input. The command also returns the verified calculation as a separate JSON field. A missing quarter produces an insufficient-evidence result with the missing period and skips the model call. The explicit snapshot and metric options let you exercise the calculation by itself.

## Step 7. Let a routing agent choose the tools

The agent returns a structured decision about the quarter, calculator metric, and a focused transcript query when search is needed. LangGraph runs the selected tools and brings their evidence together for one cited answer. A calculation-only question uses the local snapshot. Transcript search uses the vector database from Step 4. If the question requests both and one source is missing, the result reports the gap and can answer the supported portion. [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)

```powershell
uv pip install -r requirements-research.txt
.\.venv\Scripts\python.exe -m findoc.research 'How much did Infosys revenue grow year over year in the March 2026 quarter?'
.\.venv\Scripts\python.exe -m findoc.research 'What did Infosys management say about the labor-code impact on operating margins in December 2025?'
.\.venv\Scripts\python.exe -m findoc.research 'How much did Infosys revenue grow year over year in December 2025, and what did management say about the labor-code effect on margins?'
```

Read the `route` field to see what the agent selected and `gaps` to see what the tools could not provide. The third question exercises both branches and should cite the December revenue calculation and the CFO's margin explanation separately. Use `--period-end` when you want to specify the quarter yourself.

### Save the routing and citation baseline

Run the three [research smoke cases](data/research-smoke.json) against the indexed transcript and the live model:

```powershell
.\.venv\Scripts\python.exe -m findoc.baseline.research_eval
```

The cases cover a two-tool answer, a missing December 2023 comparative, and a question with no reporting period. The checks compare the route and status, verify the deterministic numbers, and confirm that expected claims cite the right type of evidence or page. The report also lists retrieved pages, which helps distinguish a retrieval miss from an answer that overlooked available evidence. The routed workflow supplies up to five transcript pages. In the first combined run, the expected page ranked fifth and fell outside the initial three-page limit. Each case has a review note for checking context and causality by hand. These are focused regression checks.

## Step 8. Investigate a management claim

The transcript investigator searches the selected call, reads the returned passages, and decides whether a more focused search would help. It can run up to two follow-up searches. Then it uses the same cited answer function. Look at the `searches` field to see the query, evidence sought, and pages returned at each step.

```powershell
.\.venv\Scripts\python.exe -m findoc.investigate 'What did Infosys management say about the labor-code impact on reported operating margin, and what adjusted free cash flow and conversion did it report?' --period-end 2025-12-31
```

Use the same indexed transcript and API settings as Step 7. The evidence scope is the earnings call, so the result describes management's statements and their qualifications. It does not independently check the filing.

## Step 9. Delegate to two specialists

The supervisor assigns a question to the financial investigator, the management investigator, or both. The financial investigator can make up to three reported-fact or year-over-year calculation calls. The management investigator uses the transcript search from Step 8 with up to two follow-ups. When both are selected, LangGraph runs them independently and passes the combined evidence to the cited answer step once.

```powershell
.\.venv\Scripts\python.exe -m findoc.supervisor 'How did Infosys revenue and profit attributable to owners change year over year in the December 2025 quarter, and how did management explain the labor-code impact on margin?'
```

The result uses the existing `status`, `claims`, and `sources` fields. It adds `assignment`, `financial_tools`, `transcript_searches`, and `gaps` for inspection. The current baseline uses the same configurable answer model for the supervisor, both specialists, and the answer step.

## Step 10. Open the web research workspace

The React interface calls the FastAPI server on the same origin. The API runs the existing single-router or supervisor workflow and returns claims, links, evidence gaps, and the selected research steps. The browser receives no model credentials.

```powershell
uv pip install -r requirements-web.txt
npm.cmd ci --prefix web
npm.cmd run build --prefix web
.\.venv\Scripts\python.exe -m uvicorn findoc.api:app --host 127.0.0.1 --port 8000
```

Open [the local research workspace](http://127.0.0.1:8000). The server reads `OPENAI_API_KEY` and `FINDOC_DATABASE_URL` from the environment or the ignored project `.env`. Questions that need transcript evidence require a running, indexed pgvector database. Financial calculations can use the local snapshots with no database connection. Keep both settings server-side.

For UI development, leave FastAPI running and run `npm.cmd run dev --prefix web` in a second terminal. Vite proxies API requests to the local FastAPI server. The production build can be served by FastAPI directly. Deploying that build to staging still requires a database with the corpus indexed and server-side credentials. [FastAPI static serving](https://fastapi.tiangolo.com/tutorial/static-files/), [Vite dev proxy](https://vite.dev/config/server-options#server-proxy)

### Try Groq from the local UI

Set `FINDOC_MODEL_PROVIDER=groq` and `GROQ_API_KEY` in the ignored `.env`, then restart FastAPI. The web app defaults to GPT-OSS 20B in Groq mode. If you previously set `FINDOC_ANSWER_MODEL`, clear the override or use a model ID available on Groq that supports strict structured outputs. Keep the indexed `FINDOC_DATABASE_URL` configured for transcript searches. [Groq API keys](https://console.groq.com/keys) · [Groq structured outputs](https://console.groq.com/docs/structured-outputs)

Select **Research Team** and ask how Infosys revenue changed year over year in December 2025 and what management said about the labor-code impact on margins. FastAPI sends the model calls to Groq. LangGraph, the calculator, and the embedding search run through the local backend. Set `FINDOC_MODEL_PROVIDER=openai` to use the OpenAI baseline in the web app.

### Run embedding inference through a hosted API

Set `FINDOC_EMBEDDING_PROVIDER=openai` with `OPENAI_API_KEY` to use `text-embedding-3-small` for both indexing and search. Reindex the two transcripts under that configuration, then start FastAPI with the same setting. The hosted index has its own version, so searches use embeddings from the selected model. PostgreSQL still stores the vectors and computes similarity on the app's database server. The default local mode uses FastEmbed for the BGE retrieval baseline. [OpenAI embedding model](https://developers.openai.com/api/docs/models/text-embedding-3-small)

### Shared PostgreSQL on the DigitalOcean VPS

The VPS runs one PostgreSQL instance with separate Trader and FinDoc databases. FastAPI serves React, calls Groq for generation, and runs BGE embeddings locally through FastEmbed.

FinDoc is reachable at [findoc.manojmathivanan.com](https://findoc.manojmathivanan.com). Cloudflare publishes a DNS-only record to the VPS. Caddy terminates HTTPS and proxies to FastAPI on loopback. The container uses the read-only database account and a persistent BGE model cache. The first hosted Research Team check reached the container's 280 MiB memory limit without restarting. Concurrent research capacity has not been measured.

The [PostgreSQL Dockerfile](deploy/postgres/Dockerfile) adds pgvector to the exact Alpine image used by Trader. Download the [pgvector source archive](https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.8.7) as `pgvector.tar.gz` into a temporary build context alongside that Dockerfile. The build verifies the archive checksum before compiling. The compiled extension files are copied into the final image.

Before cutover, preserve the running image and Compose configuration, verify a usable Trader backup, and choose a maintenance window outside scheduled Trader jobs. Swap only the PostgreSQL service image while retaining its existing data mount and settings. Verify PostgreSQL readiness, query Trader's database, and check Trader's application before creating a dedicated FinDoc database. Install pgvector there as an administrator, then index the transcripts with a dedicated indexing role and give the web role read access. If the swap fails, restore the saved image and Compose configuration with the same data mount. Check FastAPI and Trader memory together before publishing the FinDoc UI.
