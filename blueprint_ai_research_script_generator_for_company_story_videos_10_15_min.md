# Blueprint: AI Research & Script Generator for Company‑Story Videos (10–15 min)

> Goal: Input a company name → auto‑research (facts + media) → generate a fact‑checked, voiceover‑ready script (1,300–2,000 words) with shot list, timeline, citations, and asset bundle. I record VO and edit.

---

## 0) Success Criteria

- **Output**: Markdown script + shot list + asset manifest + references (URLs, timestamps) + thumbnail concepts.
- **Quality**: ≥2 independent sources per fact; confidence score per section; plagiarism check ≤5%.
- **Time**: ≤60 minutes per episode end‑to‑end on commodity hardware (excluding manual VO + edit).
- **Compliance**: Media licensing verified and logged.

---

## 1) High‑Level Architecture

- **CLI / Web UI** (Next.js/Remix) → **Orchestrator** (Prefect/Dagster) → **Pipelines**:
  1. **Discovery** (search + crawl)
  2. **Extraction** (text, metadata, transcripts)
  3. **Fact Graph** (entities, timeline, claims)
  4. **Synthesis** (outline → script → lessons → shot list)
  5. **Media** (images/video B‑roll with licenses)
  6. **QA** (cross‑check, hallucination guard, plagiarism)
  7. **Packaging** (markdown, JSON, assets zip)
- **Storage**: PostgreSQL (metadata), Object storage (S3/Backblaze), Vector DB (Qdrant/Weaviate) for RAG.
- **LLM**: GPT‑4.1+/GPT‑5 for synthesis; smaller local models for extractive tasks if desired.
- **Observability**: Prometheus + Grafana; logging with OpenTelemetry.

---

## 2) Data Sources (w/ Licensing Plan)

**Facts & Narrative**

- Wikipedia + Wikimedia (API; CC BY‑SA → must attribute)
- Company investor relations & blogs (public, cite)
- SEC/EDGAR filings (10‑K, S‑1) or global equivalents
- Quality business press: WSJ, FT, Bloomberg, NYT (respect paywalls; extract summaries from allowed portions; cite)
- HBR case studies (paid; summarize; cite)
- Podcasts/YouTube interviews (use transcripts; cite timestamps)

**Funding & Milestones**

- Crunchbase/PitchBook (API/paid) or free alternatives (CB lite; press releases)

**Media**

- Wikimedia Commons (license varies; store license + attribution)
- Pexels, Pixabay, Unsplash (API; check commercial terms)
- Company press kits (often explicitly allowed; keep terms)

**Legal/Policy Notes**

- Respect **robots.txt**; no paywall circumvention.
- Save **license JSON** alongside each asset.

---

## 3) Orchestration & Pipeline Steps

### 3.1 Orchestrator

- **Prefect** flows with tasks for each stage; retries/backoff; caching.
- Tag runs by `company_slug` and `version`.

### 3.2 Discovery

- Query multiple engines (Serper.dev/Google CSE + Bing Web, News API).
- Expand with synonyms (e.g., “IPO year”, “founder interview”, “lawsuit”, “pivot”, “acquisition”).
- Produce a **URL candidate set** ranked by authority and recency.

### 3.3 Crawling & Extraction

- Headless **Playwright** (render JS); rate‑limit; rotate proxies if needed.
- Extract: article text, author, date, section headers, quotes, named entities.
- YouTube: fetch transcript via `youtube_transcript_api`; align with timestamps.
- PDFs: parse with `pdfminer`/`pdfplumber`; OCR fallback (Tesseract) for scanned.

### 3.4 Fact Graph & Timeline

- Convert sentences → **claims** with subject/predicate/object, date, source.
- **Entity Resolution** (founder aliases, old company names).
- Build **timeline** of dated events (founding, pivots, funding, launches, crises).
- Compute **confidence** per claim: corroboration count, source reliability, date agreement.

### 3.5 Synthesis (Outline → Script)

- Create an **outline** given timeline + claims.
- Draft **script** section‑by‑section with inline citations and confidence notes.
- Produce **lessons** (generalizable insights), **hooks**, **CTAs**.
- Generate **shot list** (B‑roll ideas, graphs to render, on‑screen text) aligned by timecode.

### 3.6 Media Pipeline

- Query APIs for images/B‑roll; filter by min resolution, orientation, license.
- Download → store in `/assets/{company}/{run_id}` with `` per file.
- Optional: auto‑render simple charts (market cap over time, revenue milestones) from public data.

### 3.7 QA & Risk Controls

- **Cross‑source check**: flag claims with <2 sources or date conflicts.
- **Hallucination Guard**: Only allow LLM to **quote** from retrieved snippets; otherwise force “unknown”.
- **Plagiarism**: similarity check vs. sources; rewrite if >5% overlap.
- **Fact Spot Checks**: random 10 claims per script for manual review.

### 3.8 Packaging & Export

- Export:
  - `script.md` (voiceover‑ready)
  - `shot_list.csv` (time, visual, asset\_id)
  - `references.json` (URL, title, date, quote)
  - `assets/…` with `license.json`
  - `thumbnail_prompts.txt` (3 concepts with text overlays)
- Create a zip and optionally auto‑open in Notion/GDrive.

---

## 4) Data Model (PostgreSQL)

```sql
-- Companies
CREATE TABLE companies (
  id UUID PRIMARY KEY,
  slug TEXT UNIQUE,
  name TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Sources
CREATE TABLE sources (
  id UUID PRIMARY KEY,
  company_id UUID REFERENCES companies(id),
  url TEXT, domain TEXT, title TEXT,
  author TEXT, published_at TIMESTAMPTZ,
  content TEXT,
  license JSONB,
  reliability INT, -- 1..5 heuristics
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Claims
CREATE TABLE claims (
  id UUID PRIMARY KEY,
  company_id UUID REFERENCES companies(id),
  claim TEXT,
  claim_date DATE,
  subject TEXT, predicate TEXT, object TEXT,
  confidence REAL,
  corroboration_count INT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Claim ↔ Source mapping
CREATE TABLE claim_sources (
  claim_id UUID REFERENCES claims(id),
  source_id UUID REFERENCES sources(id),
  quote TEXT,
  start_char INT, end_char INT,
  PRIMARY KEY (claim_id, source_id)
);

-- Media assets
CREATE TABLE media_assets (
  id UUID PRIMARY KEY,
  company_id UUID REFERENCES companies(id),
  path TEXT,
  source_url TEXT,
  width INT, height INT,
  license JSONB,
  safe_for_use BOOLEAN,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 5) Component Design (Agents & Prompts)

### 5.1 Retrieval Agent ("Researcher")

**Input**: company name, synonyms list.\
**Instruction**: “Gather top 50 URLs across categories (founding, funding, interviews, crises, competition, products, lawsuits, pivots, acquisitions). Return JSON with url, title, category, rationale.”

### 5.2 Extractor

**Instruction**: “From this page text, extract dated facts and quotes. Output JSONL of {claim, date, evidence\_snippet, source\_url}. Do not infer.”

### 5.3 Fact‑Checker

**Instruction**: “Given candidate claims + sources, compute confidence 0–1. High confidence requires ≥2 independent sources that agree on date within ±30 days.”

### 5.4 Outliner

**Instruction**: “Create a 9‑part outline for a 10–15 min video: Hook, Founding, Early Struggles, Breakthrough, Scaling, Setbacks, Now, Competitors, Lessons. Allocate target word counts per section to total 1,600 words. Include visual suggestions per section.”

### 5.5 Scriptwriter

**Instruction**: “Write a narration‑ready script in an engaging but concise tone. Use clear timestamps and **[ref****:n****]** citation tags at the end of paragraphs. Use foreshadowing in Hook. Keep sentences VO‑friendly.”

### 5.6 Lesson Synthesizer

**Instruction**: “From confirmed claims, derive 5–7 actionable lessons. Tie each to a specific moment in the story.”

### 5.7 Thumbnail/Title Generator

**Instruction**: “Propose 5 titles (≤60 chars) and 3 thumbnail concepts with 2–3 word overlays.”

---

## 6) Script Template (10–15 min, \~1,600 words)

- **Hook (120–180 words)** – provocative moment or ‘near‑death’ event.
- **Founding (180–220)** – who/why/context.
- **Early Challenges (180–220)** – funding, market skepticism, operations.
- **Breakthrough/Pivot (180–220)** – what changed and why.
- **Scaling (180–220)** – hiring, marketing, capital, product velocity.
- **Setbacks (150–200)** – lawsuits, PR, failures.
- **Now & Metrics (120–180)** – valuation, users, revenue bands.
- **Competitive Landscape (120–160)** – how they defend.
- **Lessons (220–280)** – numbered takeaways with examples.
- **CTA (60–90)** – like/subscribe + next episode tease.

**Formatting**: scene markers + suggested visuals per paragraph; e.g.,

```
[00:00] HOOK — Visual: newsroom headlines montage
Narration: ... [ref:1][ref:2]
```

---

## 7) Example Output (Excerpt – Netflix)

```
[00:00] HOOK — Visual: Blockbuster store closing sign.
Narration: In 2000, Netflix offered to sell for $50M. Blockbuster passed. That snub forced Netflix to double down on a risky idea: subscriptions by mail. [ref:1][ref:2]

[01:10] FOUNDING — Visual: 1990s web screenshots; red envelopes.
Narration: Reed Hastings and Marc Randolph launched Netflix in 1997 after a $40 late fee nudged them to rethink home video. Early tests showed pay‑per‑rental didn’t work; flat‑fee subscriptions did. [ref:3][ref:4]
```

*(Full script would include references mapping [ref**:n**] → URLs.)*

---

## 8) CLI & Workflow

```bash
# 1) New project
ai-vid new "Netflix" --region=US

# 2) Run full pipeline
ai-vid run --company "Netflix" --fast --max-sources 60

# 3) Open results
open output/netflix/2025-08-14/
# script.md, shot_list.csv, references.json, assets/
```

**Config (**``**)**

```yaml
engines:
  web_search: bing
  llm_model: gpt-5
limits:
  max_concurrent_requests: 6
  per_claim_min_sources: 2
  plagiarism_threshold: 0.05
licenses:
  allow_unsplash: true
  require_attribution: true
```

---

## 9) Cost & Performance Estimate (per episode)

- Web search + crawling: \$0.50–\$1.50 (Serper/Bing API)
- LLM synthesis (1–2 full drafts + checks): \$1.50–\$5.00 (model‑dependent)
- Transcripts via YouTube: free
- Stock media: \$0 (free libs) – \$10 (paid B‑roll)
- **Total**: \~\$2–\$15/episode in API spend (excluding paid databases).

**Runtime**: 20–50 min depending on sources and retries.

---

## 10) Risk Register & Mitigations

- **Hallucination** → Retrieval‑augmented prompts; require citations; fail closed to “unknown”.
- **Copyright** → Only store/download assets with explicit commercial‑use license; attach `license.json`.
- **Defamation** → Exclude unverified allegations; flag legal‑sensitive claims for manual review.
- **Paywall/ToS** → Respect terms; use official APIs when required.
- **Regional Bias** → Diversify sources; include local press when applicable.

---

## 11) QA Checklist (Pre‑Publish)

1. Every paragraph ends with [ref\:n].
2. Each [ref\:n] has ≥2 independent sources where possible.
3. Dates match across sources (±30 days) or are annotated.
4. All images in shot list have license and attribution text.
5. Plagiarism <5%; run rephrase pass if flagged.
6. Lessons map to specific story beats.
7. Thumbnail/title A/B option
