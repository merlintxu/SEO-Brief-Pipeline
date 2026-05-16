# Google AI Search Skill Analysis

This analysis compares the current SEO Brief Pipeline against the attached
`google-ai-search-optimization` skill and Google's official generative AI Search
guidance.

Verified source:

- Google's guide to optimizing for generative AI features on Google Search.
- The official page was checked on 2026-05-16 and showed "Last updated
  2026-05-15 UTC".

## Executive Readout

The project already has a strong operational base:

- client/project configuration,
- provider preflight,
- SEMrush and SERP collection,
- competitor audit,
- optional GSC and GA4 enrichment,
- typed stage contracts,
- quality gates,
- LLM gateway,
- DB-first outputs,
- Gradio operator console.

The main gap is not plumbing. The main gap is that the generated briefing is
still mostly a SERP/keyword/content-structure brief. The attached skill pushes a
broader Google AI Search readiness model:

- crawlability and indexability,
- non-commodity content and firsthand expertise,
- media requirements,
- structured data accuracy,
- ecommerce/local readiness,
- agent-friendly site usability,
- myth rejection around AEO/GEO hacks.

The project should turn those ideas into typed signals, gates, prompt inputs and
operator-facing checks.

## What The Skill Adds

The skill's strongest contribution is its operating model:

Google AI Overviews and AI Mode should be treated as Google Search features
grounded in Google's Search index, not as a separate optimization system. The
practical work remains:

- make pages crawlable and indexable,
- make content useful and distinctive,
- make media and structured data accurate,
- make product/local facts machine-readable where relevant,
- make pages usable for people and browser agents.

The skill also explicitly rejects tactics that should not become product
features:

- `llms.txt` as a Google AI Search requirement,
- special AI-only Markdown pages,
- artificial content chunking,
- mass long-tail page generation,
- fake mentions or citations,
- AI-specific schema markup.

## Current Project Fit

### Strong Matches

The current pipeline already supports several skill recommendations:

- Search-index grounding:
  - SERP acquisition and competitor audit are central.
- People-first briefing structure:
  - `SEOBriefing` captures headings, FAQs, links, multimedia suggestions and
    E-E-A-T notes.
- Measurement:
  - GSC and GA4 are optional enrichment sources.
- Operational safety:
  - provider checks and config preflight avoid blind runs.
- Structured outputs:
  - final briefing is validated by Pydantic.

### Missing Or Thin Areas

The current pipeline does not yet deeply evaluate:

- target URL crawlability and indexability,
- canonical tags,
- robots/noindex,
- sitemap presence,
- rendered JavaScript content,
- internal link crawlability,
- image SEO,
- video SEO,
- page experience,
- author/reviewer/trust signals,
- ecommerce and local business facts,
- agent-friendly DOM/accessibility readiness,
- content originality beyond competitor gap summaries.

## Recommended Product Additions

### 1. Add Google AI Search Readiness Audit

Add a new stage after competitor audit and before briefing generation:

```text
target_url or base_domain
  -> technical readiness audit
  -> content trust audit
  -> media/schema audit
  -> agent-friendly audit
  -> readiness score + findings
```

Suggested module:

```text
seo_pipeline/ai_search_readiness.py
```

Suggested models:

```text
AiSearchReadinessReport
AiSearchFinding
TechnicalEligibilitySignals
ContentValueSignals
MediaSeoSignals
StructuredDataReadiness
AgentFriendlySignals
```

This should run differently by brief type:

- `new_page`: generate requirements and checks for the future page.
- `existing_page`: audit the real target URL.

### 2. Expand Existing URL Audit

For `existing_page`, `audit_single_url()` should inspect the target URL itself,
not only competitors.

Add target URL signals:

- status code,
- canonical URL,
- robots meta,
- `x-robots-tag` if headers are available,
- title and meta description quality,
- heading structure,
- word count and main content extraction quality,
- schema types,
- image count and missing alt text,
- video presence,
- internal/external link counts,
- author/reviewer/date signals,
- visible support/contact/about signals where relevant.

Persist as:

```text
target_audit_report.json
run_metrics.stages.target_audit
```

### 3. Turn Content Quality Into Typed Gates

Current quality gates check minimum data coverage. Add briefing quality gates
that reflect the skill:

- unique angle is not generic,
- headings cover intent and PAA naturally,
- no fake freshness,
- no unsupported claims,
- author/trust notes included for YMYL-like topics,
- media suggestions are concrete,
- structured data recommendations match visible page type,
- internal links reference owned domain only.

Suggested module:

```text
seo_pipeline/brief_quality.py
```

### 4. Improve Prompt Registry

Current registry has only:

```text
brief_generator/v1
```

Add prompt families:

```text
ai_search_readiness_auditor
content_value_planner
technical_seo_reviewer
brief_quality_reviewer
myth_checker
```

Use them as deterministic stages where possible and LLM-reviewed stages only
where necessary.

### 5. Add Myth And Policy Guardrails

The system should explicitly avoid recommending:

- `llms.txt` as a Google AI Search lever,
- content chunking for AI,
- mass variants for query fan-out,
- fake citations or mentions,
- schema as an AI-only hack.

Add these as:

- prompt constraints,
- reviewer checks,
- documentation,
- optional UI warnings if an operator asks for these outputs.

### 6. Add Media Requirements To Briefings

`SEOBriefing.multimedia_suggestions` exists but is too generic. Expand it into
typed media requirements:

```text
MediaRequirement
  type: image | video | table | chart | comparison
  placement
  purpose
  alt_text_guidance
  source_or_creation_notes
  validation
```

This aligns better with Google image/video Search opportunities.

### 7. Add Ecommerce And Local Project Modes

Projects should declare vertical intent:

```text
project_type:
  content
  ecommerce
  local
  saas
  marketplace
```

For ecommerce:

- Product schema,
- Merchant Center,
- price/availability/shipping/returns,
- product imagery,
- reviews.

For local:

- Business Profile,
- NAP consistency,
- hours,
- services,
- local schema,
- support/contact details.

### 8. Add Agent-Friendly Website Checks

The skill includes browser-agent readiness. This can become a future optional
Playwright-based audit:

- clickable elements have semantic controls,
- forms have labels,
- important actions are visible,
- no hidden overlays block tasks,
- important content is text/DOM-visible,
- layout is stable enough for agent interaction.

This is especially useful for ecommerce, booking and lead-gen pages.

## Proposed Backlog

### PR AISEO1 - AI Search Readiness Contracts

Status: implemented baseline.

- Add models for readiness reports and findings.
- Add deterministic checklist evaluator for known HTML signals.
- Add tests with HTML fixtures.

### PR AISEO2 - Target URL Audit Stage

Status: implemented baseline.

- Audit the target URL for existing-page runs.
- Persist `target_audit_report.json`.
- Add stage metrics.

### PR AISEO3 - Briefing Prompt Upgrade

Status: implemented baseline.

- Add prompt registry entries for AI Search readiness.
- Inject readiness findings into planner/writer context.
- Add myth guardrails.

### PR AISEO4 - Brief Quality Reviewer

Status: implemented baseline.

- Add post-generation review against content value, evidence, media, trust and
  unsupported tactic rules.
- Persist reviewer results in `run_metrics.json`.

### PR AISEO5 - Vertical Modes

Status: implemented baseline.

- Add `project_type` to project config.
- Add ecommerce/local-specific checks and briefing requirements.
- Surface project type in Gradio.

### PR AISEO6 - Agent-Friendly Audit

Status: implemented baseline.

- Add optional browser/DOM audit for pages where task completion matters.
- Keep it opt-in due to runtime cost.

## Risks

- Adding too many checklist fields can make briefings bureaucratic. The system
  should prioritize findings with evidence and impact.
- Live URL audits can be slow or blocked. They must remain bounded, cached and
  non-fatal when enough other data exists.
- Google guidance changes. Any policy-sensitive recommendation should point to
  official docs and be periodically reviewed.

## Recommended Next Step

Next hardening step: improve target URL fetching so the same HTML payload feeds
both `target_audit_report.json` and `ai_search_readiness.json`, then add more
HTML fixtures for ecommerce/local pages.
