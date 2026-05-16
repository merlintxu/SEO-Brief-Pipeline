"""Google AI Search readiness checks.

These checks operationalize Google's AI Search guidance as deterministic,
bounded signals. They are not ranking guarantees and intentionally avoid
unsupported AEO/GEO shortcuts.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from seo_pipeline.models import (
    AgentFriendlySignals,
    AiSearchFinding,
    AiSearchReadinessReport,
    AuditEntry,
    AuditReport,
    BriefQualityReview,
    ContentValueSignals,
    MediaSeoSignals,
    SEOBriefing,
    StructuredDataReadiness,
    TechnicalEligibilitySignals,
)
from seo_pipeline.utils.text import normalize_ws
from seo_pipeline.vendors.scrapers import scrape_with_failover


MYTH_GUARDRAILS = (
    "Do not recommend llms.txt as a Google AI Search requirement.",
    "Do not recommend AI-only Markdown or special text mirrors.",
    "Do not split content into tiny chunks solely for AI systems.",
    "Do not create near-duplicate pages for every query fan-out variant.",
    "Do not recommend fake citations, fake mentions, or manufactured reputation.",
    "Do not describe structured data as an AI-specific ranking hack.",
)


def audit_target_url(
    target_url: str,
    *,
    project_type: str = "content",
    piloterr_key: str | None = None,
    dataforseo_login: str | None = None,
    dataforseo_password: str | None = None,
    timeout: int = 20,
) -> AuditReport:
    """Audit one existing target URL with Google AI Search readiness signals."""
    started = time.perf_counter()
    entry = AuditEntry(url=target_url)
    html = scrape_with_failover(
        url=target_url,
        piloterr_key=piloterr_key,
        dataforseo_login=dataforseo_login,
        dataforseo_password=dataforseo_password,
        timeout=timeout,
    )
    if not html:
        entry.status_code = 0
        entry.elapsed_ms = round((time.perf_counter() - started) * 1000)
        entry.errors.append("No response")
        return AuditReport(label="target_url_audit", entries=[entry], generated_at=datetime.now().isoformat(timespec="seconds"))

    _populate_audit_entry_from_html(entry, html, started)
    report = build_readiness_report_from_html(
        target_url,
        html,
        audit_entry=entry,
        mode="existing_page",
        project_type=project_type,
    )
    entry.errors.extend([finding.issue for finding in report.findings if finding.severity == "error"])
    return AuditReport(label="target_url_audit", entries=[entry], generated_at=datetime.now().isoformat(timespec="seconds"))


def build_readiness_for_new_page(*, keyword: str, project_type: str = "content", base_domain: str = "") -> AiSearchReadinessReport:
    findings = [
        AiSearchFinding(
            category="content",
            severity="warning",
            issue="New page needs original value requirements.",
            evidence=f"keyword={keyword}",
            recommendation="Include firsthand evidence, examples, data, media or expert analysis beyond competitor summaries.",
            validation="Review final draft for original examples and proof points.",
        ),
        AiSearchFinding(
            category="technical",
            severity="info",
            issue="Future page must be crawlable and indexable.",
            evidence=base_domain,
            recommendation="Publish on a stable URL returning 200, linked internally, included in sitemap and not blocked by robots/noindex.",
            validation="Use Search Console URL Inspection after publication.",
        ),
        AiSearchFinding(
            category="myth",
            severity="info",
            issue="Avoid AI Search shortcuts.",
            evidence="Google AI Search uses normal Search fundamentals.",
            recommendation="Do not add llms.txt, fake citations, AI-only mirrors or mass fan-out pages as visibility tactics.",
            validation="Confirm recommendations improve users, crawlability, indexability, understanding or trust.",
        ),
    ]
    if project_type in {"ecommerce", "marketplace"}:
        findings.append(
            AiSearchFinding(
                category="ecommerce",
                severity="warning",
                issue="Commerce facts must be explicit and fresh.",
                evidence=f"project_type={project_type}",
                recommendation="Plan Product data, price, availability, shipping, returns, reviews and high-quality product media.",
                validation="Validate Product structured data and Merchant Center diagnostics.",
            )
        )
    if project_type == "local":
        findings.append(
            AiSearchFinding(
                category="local",
                severity="warning",
                issue="Local business facts must be consistent.",
                evidence="project_type=local",
                recommendation="Plan NAP, hours, service area, Business Profile consistency and LocalBusiness/Organization markup.",
                validation="Compare page facts with Google Business Profile.",
            )
        )
    return AiSearchReadinessReport(
        url=base_domain,
        mode="new_page",
        project_type=project_type,
        score=70,
        verdict="Planning requirements generated for a new page.",
        findings=findings,
    )


def build_readiness_from_audit_entry(
    entry: AuditEntry,
    *,
    mode: str = "existing_page",
    project_type: str = "content",
) -> AiSearchReadinessReport:
    technical = TechnicalEligibilitySignals(
        status_code=entry.status_code,
        indexable=entry.status_code == 200,
        has_title=bool(entry.title),
        has_meta_description=bool(entry.meta_desc),
        has_crawlable_links=False,
        has_stable_url=bool(urlparse(entry.url).scheme and urlparse(entry.url).netloc),
    )
    heading_count = sum(len(values) for values in entry.headings.values())
    content = ContentValueSignals(
        word_count=entry.word_count,
        has_h1=bool(entry.h1),
        heading_count=heading_count,
        commodity_risk="high" if entry.word_count < 500 or heading_count < 3 else "medium" if entry.word_count < 1200 else "low",
    )
    structured = StructuredDataReadiness(
        schema_types=entry.schema_signals.schema_types,
        has_article=entry.schema_signals.has_article,
        has_product=entry.schema_signals.has_product,
        has_breadcrumb=entry.schema_signals.has_breadcrumb,
        has_faq=entry.schema_signals.has_faq,
    )
    media = MediaSeoSignals()
    agent = AgentFriendlySignals(important_content_in_text=entry.word_count >= 100)
    findings = _build_findings(
        url=entry.url,
        project_type=project_type,
        technical=technical,
        content=content,
        media=media,
        structured=structured,
        agent=agent,
    )
    score = _score_readiness(findings)
    return AiSearchReadinessReport(
        url=entry.url,
        mode=mode,
        project_type=project_type,
        score=score,
        verdict=_verdict(score),
        technical=technical,
        content=content,
        media=media,
        structured_data=structured,
        agent_friendly=agent,
        findings=findings,
    )


def build_readiness_report_from_html(
    url: str,
    html: str,
    *,
    audit_entry: AuditEntry | None = None,
    mode: str = "existing_page",
    project_type: str = "content",
) -> AiSearchReadinessReport:
    soup = BeautifulSoup(html or "", "lxml")
    entry = audit_entry or AuditEntry(url=url)
    if audit_entry is None:
        _populate_audit_entry_from_soup(entry, soup, 0.0)

    technical = _technical_signals(url, soup, entry)
    content = _content_signals(soup, entry)
    media = _media_signals(soup)
    structured = _structured_data_signals(soup)
    agent = _agent_friendly_signals(soup)
    findings = _build_findings(
        url=url,
        project_type=project_type,
        technical=technical,
        content=content,
        media=media,
        structured=structured,
        agent=agent,
    )
    score = _score_readiness(findings)
    verdict = _verdict(score)
    return AiSearchReadinessReport(
        url=url,
        mode=mode,
        project_type=project_type,
        score=score,
        verdict=verdict,
        technical=technical,
        content=content,
        media=media,
        structured_data=structured,
        agent_friendly=agent,
        findings=findings,
    )


def review_briefing_for_ai_search(
    briefing: SEOBriefing,
    readiness: AiSearchReadinessReport | None,
    *,
    project_type: str = "content",
) -> BriefQualityReview:
    findings: list[AiSearchFinding] = []
    if len(briefing.headings) < 8:
        findings.append(_finding("content", "error", "Briefing has too few sections.", str(len(briefing.headings)), "Add enough sections to satisfy the task comprehensively.", "Validate SEOBriefing.headings length."))
    if len(briefing.unique_angle.strip()) < 20:
        findings.append(_finding("content", "warning", "Unique angle is weak or generic.", briefing.unique_angle, "Require a specific differentiator based on evidence or firsthand value.", "Review unique_angle manually."))
    if not briefing.eeat_notas.strip():
        findings.append(_finding("trust", "warning", "E-E-A-T notes are missing.", "", "Add author, reviewer, evidence, methodology or trust requirements.", "Check eeat_notas."))
    if len(briefing.multimedia_suggestions) < 1:
        findings.append(_finding("media", "warning", "No media requirements were generated.", "", "Add concrete image, video, table or comparison suggestions.", "Check multimedia_suggestions."))
    text_blob = " ".join(
        [
            briefing.meta_title,
            briefing.meta_description,
            briefing.h1,
            briefing.unique_angle,
            briefing.eeat_notas,
            " ".join(section.title + " " + section.content for section in briefing.headings),
        ]
    ).lower()
    unsupported_terms = ["llms.txt", "fake citation", "fake mention", "ai-only", "chunking for ai"]
    for term in unsupported_terms:
        if term in text_blob:
            findings.append(_finding("myth", "error", f"Unsupported tactic mentioned: {term}", term, "Remove unsupported AI Search shortcut recommendations.", "Review final briefing text."))
    if project_type in {"ecommerce", "marketplace"} and "product" not in text_blob and "merchant" not in text_blob:
        findings.append(_finding("ecommerce", "warning", "Commerce-specific requirements are missing.", project_type, "Add product data, Merchant Center, price, availability, returns or review requirements.", "Review ecommerce brief requirements."))
    if project_type == "local" and "business" not in text_blob and "local" not in text_blob:
        findings.append(_finding("local", "warning", "Local-specific requirements are missing.", project_type, "Add Business Profile, NAP, hours, services or LocalBusiness requirements.", "Review local brief requirements."))
    if readiness and readiness.findings and not any("readiness" in section.content.lower() for section in briefing.headings):
        findings.append(_finding("ai_search", "info", "Readiness findings should be considered in editorial QA.", readiness.verdict, "Review readiness findings before publishing.", "Compare brief against readiness report."))

    score = max(0, 100 - sum(25 if item.severity == "error" else 10 if item.severity == "warning" else 0 for item in findings))
    return BriefQualityReview(passed=not any(item.severity == "error" for item in findings), score=score, findings=findings)


def myth_guardrails_text() -> str:
    return "\n".join(f"- {item}" for item in MYTH_GUARDRAILS)


def readiness_context_text(report: AiSearchReadinessReport | None) -> str:
    if report is None:
        return "No AI Search readiness report available."
    findings = "\n".join(
        f"- [{item.severity}] {item.category}: {item.issue} -> {item.recommendation}"
        for item in report.findings[:12]
    )
    return (
        f"Mode: {report.mode}\n"
        f"Project type: {report.project_type}\n"
        f"Score: {report.score}\n"
        f"Verdict: {report.verdict}\n"
        f"Findings:\n{findings or '- none'}"
    )


def _populate_audit_entry_from_html(entry: AuditEntry, html: str, started: float) -> None:
    soup = BeautifulSoup(html, "lxml")
    _populate_audit_entry_from_soup(entry, soup, started)


def _populate_audit_entry_from_soup(entry: AuditEntry, soup: BeautifulSoup, started: float) -> None:
    title_tag = soup.find("title")
    entry.title = normalize_ws(title_tag.get_text()) if title_tag else ""
    entry.status_code = 200 if entry.status_code == 0 else entry.status_code
    h1 = soup.find("h1")
    entry.h1 = normalize_ws(h1.get_text()) if h1 else ""
    meta_desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    entry.meta_desc = meta_desc.get("content", "") if meta_desc else ""
    text = soup.get_text(separator=" ")
    entry.word_count = len(normalize_ws(text).split())
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            heading = normalize_ws(tag.get_text())
            if heading:
                entry.headings.setdefault(f"H{level}", []).append(heading)
    structured = _structured_data_signals(soup)
    entry.schema_signals.has_article = structured.has_article
    entry.schema_signals.has_product = structured.has_product
    entry.schema_signals.has_breadcrumb = structured.has_breadcrumb
    entry.schema_signals.has_faq = structured.has_faq
    entry.schema_signals.schema_types = structured.schema_types[:5]
    entry.elapsed_ms = round((time.perf_counter() - started) * 1000) if started else 0


def _technical_signals(url: str, soup: BeautifulSoup, entry: AuditEntry) -> TechnicalEligibilitySignals:
    robots = _meta_content(soup, "robots")
    googlebot = _meta_content(soup, "googlebot")
    robots_combined = ", ".join(item for item in (robots, googlebot) if item)
    canonical = ""
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical_tag:
        canonical = canonical_tag.get("href", "").strip()
    parsed = urlparse(url)
    return TechnicalEligibilitySignals(
        status_code=entry.status_code,
        indexable=entry.status_code == 200 and "noindex" not in robots_combined.lower(),
        robots_meta=robots_combined,
        canonical_url=canonical,
        has_title=bool(entry.title),
        has_meta_description=bool(entry.meta_desc),
        has_crawlable_links=bool(soup.find("a", href=True)),
        has_stable_url=bool(parsed.scheme and parsed.netloc),
    )


def _content_signals(soup: BeautifulSoup, entry: AuditEntry) -> ContentValueSignals:
    text = normalize_ws(soup.get_text(" ")).lower()
    author_terms = ("author", "autor", "reviewed by", "revisado por", "expert", "experto")
    trust_terms = ("about us", "sobre nosotros", "contact", "contacto", "methodology", "metodologia", "metodología", "sources", "fuentes")
    date_terms = ("updated", "actualizado", "published", "publicado", "datepublished", "datemodified")
    heading_count = sum(len(values) for values in entry.headings.values())
    commodity_risk = "high" if entry.word_count < 500 or heading_count < 3 else "medium" if entry.word_count < 1200 else "low"
    return ContentValueSignals(
        word_count=entry.word_count,
        has_h1=bool(entry.h1),
        heading_count=heading_count,
        has_author_signal=any(term in text for term in author_terms) or bool(soup.find(attrs={"rel": "author"})),
        has_date_signal=any(term in text for term in date_terms) or bool(soup.find("time")),
        has_trust_signal=any(term in text for term in trust_terms),
        commodity_risk=commodity_risk,
    )


def _media_signals(soup: BeautifulSoup) -> MediaSeoSignals:
    images = soup.find_all("img")
    missing_alt = sum(1 for image in images if not image.get("alt", "").strip())
    videos = soup.find_all(["video", "iframe"])
    return MediaSeoSignals(
        image_count=len(images),
        images_missing_alt=missing_alt,
        video_count=len(videos),
        has_descriptive_media=bool(images) and missing_alt < len(images),
    )


def _structured_data_signals(soup: BeautifulSoup) -> StructuredDataReadiness:
    schema_types: list[str] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        schema_types.extend(_extract_schema_types(payload))
    joined = " ".join(schema_types)
    return StructuredDataReadiness(
        schema_types=schema_types[:25],
        has_article="Article" in joined or "NewsArticle" in joined or "BlogPosting" in joined,
        has_product="Product" in joined,
        has_breadcrumb="BreadcrumbList" in joined,
        has_faq="FAQPage" in joined,
        has_local_business="LocalBusiness" in joined,
        has_organization="Organization" in joined,
    )


def _extract_schema_types(payload: object) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        item_type = payload.get("@type")
        if isinstance(item_type, str):
            found.append(item_type)
        elif isinstance(item_type, list):
            found.extend(str(item) for item in item_type)
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found.extend(_extract_schema_types(item))
        for value in payload.values():
            if isinstance(value, dict):
                found.extend(_extract_schema_types(value))
            elif isinstance(value, list):
                for item in value:
                    found.extend(_extract_schema_types(item))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_extract_schema_types(item))
    return found


def _agent_friendly_signals(soup: BeautifulSoup) -> AgentFriendlySignals:
    inputs = soup.find_all(["input", "textarea", "select"])
    labeled_ids = {label.get("for") for label in soup.find_all("label") if label.get("for")}
    with_labels = 0
    without_labels = 0
    for control in inputs:
        control_id = control.get("id")
        has_label = bool(control_id and control_id in labeled_ids) or bool(control.get("aria-label")) or bool(control.get("name"))
        if has_label:
            with_labels += 1
        else:
            without_labels += 1
    empty_controls = 0
    for control in soup.find_all(["button", "a"]):
        text = normalize_ws(control.get_text(" "))
        if not text and not control.get("aria-label") and not control.get("title"):
            empty_controls += 1
    return AgentFriendlySignals(
        buttons_count=len(soup.find_all("button")),
        links_count=len(soup.find_all("a", href=True)),
        inputs_with_labels=with_labels,
        inputs_without_labels=without_labels,
        suspicious_empty_controls=empty_controls,
        important_content_in_text=len(normalize_ws(soup.get_text(" ")).split()) >= 100,
    )


def _build_findings(
    *,
    url: str,
    project_type: str,
    technical: TechnicalEligibilitySignals,
    content: ContentValueSignals,
    media: MediaSeoSignals,
    structured: StructuredDataReadiness,
    agent: AgentFriendlySignals,
) -> list[AiSearchFinding]:
    findings: list[AiSearchFinding] = []
    if not technical.indexable:
        findings.append(_finding("technical", "error", "Page is not clearly indexable.", f"status={technical.status_code}, robots={technical.robots_meta}", "Return 200 and remove noindex or blocking directives for pages intended to appear in Search.", "Use Search Console URL Inspection."))
    if not technical.has_title or not technical.has_meta_description:
        findings.append(_finding("technical", "warning", "Title or meta description is missing.", f"title={technical.has_title}, meta={technical.has_meta_description}", "Add unique, descriptive title and meta description.", "Inspect rendered HTML."))
    if not technical.has_crawlable_links:
        findings.append(_finding("technical", "warning", "No crawlable internal links detected.", url, "Use normal anchor links for important navigation and related content.", "Crawl the rendered page and inspect links."))
    if content.commodity_risk == "high":
        findings.append(_finding("content", "warning", "Content appears thin or under-structured.", f"words={content.word_count}, headings={content.heading_count}", "Add original evidence, examples, detail and useful structure.", "Review word count, headings and original proof points."))
    if not content.has_author_signal:
        findings.append(_finding("trust", "info", "Author or expertise signal not detected.", "", "Add author, reviewer or expert context where useful.", "Inspect visible author/reviewer information."))
    if not content.has_trust_signal:
        findings.append(_finding("trust", "info", "Trust/support/about signals not detected.", "", "Add relevant support, contact, sourcing, methodology or about context.", "Inspect visible trust signals."))
    if media.image_count and media.images_missing_alt:
        findings.append(_finding("media", "warning", "Some images are missing alt text.", f"{media.images_missing_alt}/{media.image_count}", "Add descriptive alt text for meaningful images.", "Run image SEO/accessibility check."))
    if not structured.has_breadcrumb:
        findings.append(_finding("structured_data", "info", "Breadcrumb structured data not detected.", ",".join(structured.schema_types), "Add BreadcrumbList when page hierarchy is visible and accurate.", "Validate with Rich Results Test."))
    if project_type in {"ecommerce", "marketplace"} and not structured.has_product:
        findings.append(_finding("ecommerce", "warning", "Product structured data not detected for commerce project.", project_type, "Add Product data matching visible product, offer, shipping and return information.", "Validate Product rich result eligibility."))
    if project_type == "local" and not structured.has_local_business:
        findings.append(_finding("local", "warning", "LocalBusiness structured data not detected for local project.", project_type, "Add accurate LocalBusiness/Organization details matching visible business facts.", "Compare with Google Business Profile."))
    if agent.inputs_without_labels or agent.suspicious_empty_controls:
        findings.append(_finding("agent_friendly", "warning", "Some controls may be hard for browser agents or assistive tech.", f"unlabeled_inputs={agent.inputs_without_labels}, empty_controls={agent.suspicious_empty_controls}", "Use native controls, labels, accessible names and visible action states.", "Inspect DOM and accessibility tree."))
    return findings


def _score_readiness(findings: Iterable[AiSearchFinding]) -> int:
    score = 100
    for finding in findings:
        if finding.severity == "error":
            score -= 30
        elif finding.severity == "warning":
            score -= 12
        else:
            score -= 3
    return max(0, min(100, score))


def _verdict(score: int) -> str:
    if score >= 85:
        return "Strong Google AI Search readiness baseline."
    if score >= 65:
        return "Usable baseline with priority improvements."
    if score >= 40:
        return "Significant readiness gaps should be fixed."
    return "Major eligibility or quality blockers detected."


def _finding(category: str, severity: str, issue: str, evidence: str, recommendation: str, validation: str) -> AiSearchFinding:
    return AiSearchFinding(
        category=category,
        severity=severity,
        issue=issue,
        evidence=evidence,
        recommendation=recommendation,
        validation=validation,
    )


def _meta_content(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": re.compile(f"^{re.escape(name)}$", re.I)})
    return tag.get("content", "").strip() if tag else ""
