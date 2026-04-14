from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from readability import Document

from src.models import JobPosting

COMMON_KEYWORDS = {
    "python", "sql", "excel", "tableau", "power bi", "aws", "azure", "gcp",
    "product management", "stakeholder management", "project management", "agile",
    "analytics", "data analysis", "machine learning", "communication", "leadership",
    "java", "javascript", "typescript", "react", "node", "api", "salesforce",
    "docker", "kubernetes", "ci/cd", "etl", "a/b testing", "forecasting",
    "power automate", "t-sql", "sql server", "data governance", "data quality",
    "data engineering", "business intelligence", "reporting", "dax", "sharepoint",
}

# Browser-like headers to avoid 403s on job sites
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Page <title> suffixes that are NOT the job title — strip these
_TITLE_NOISE = re.compile(
    r"\s*[\|\-–—·•]\s*(careers|jobs|apply|job search|linkedin|indeed|"
    r"glassdoor|workday|lever|greenhouse|icims|taleo|smartrecruiters|"
    r"reasonable accommodation|aon|guitar center|.*?inc\.?|.*?llc\.?)",
    flags=re.IGNORECASE,
)


class JobSourceError(RuntimeError):
    pass


class JobFetchError(RuntimeError):
    """Raised when a URL cannot be fetched — caller should skip and continue."""
    pass


def load_job_sources(path: Path) -> list[str]:
    if not path.exists():
        raise JobSourceError(f"Job source file not found: {path}")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    sources = [line for line in lines if line and not line.startswith("#")]
    if not sources:
        raise JobSourceError(
            "No job links found. Add one URL per line in data/input/job_links.txt"
        )
    return sources


def parse_job_source(source: str, timeout: int = 25) -> JobPosting:
    if source.lower().startswith(("http://", "https://")):
        return _parse_job_url(source, timeout)
    text_path = Path(source)
    if text_path.exists():
        text = text_path.read_text(encoding="utf-8", errors="ignore")
        return _parse_text_job(text=text, source=source)
    raise JobSourceError(f"Unsupported job source: {source}")


def _parse_job_url(url: str, timeout: int) -> JobPosting:
    try:
        session = requests.Session()
        session.headers.update(_HEADERS)
        # First request — let the site set cookies (helps with bot detection)
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        html = response.text
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        raise JobFetchError(
            f"HTTP {status} fetching {url}. "
            f"This site blocks scrapers. Save the job description as a .txt file "
            f"in data/input/ and add the file path to job_links.txt instead."
        ) from e
    except requests.exceptions.RequestException as e:
        raise JobFetchError(f"Network error fetching {url}: {e}") from e

    return _parse_html_job(url, html)


def _parse_html_job(url: str, html: str) -> JobPosting:
    text = _extract_main_text(html)
    title, company, location = _extract_metadata(html, text)
    return JobPosting(
        url=url,
        title=title,
        company=company,
        location=location,
        text=text,
        keywords=_extract_keywords(text),
    )


def _parse_text_job(text: str, source: str) -> JobPosting:
    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "Target Role")
    return JobPosting(
        url=source,
        title=first_line[:120],
        company="",
        location="",
        text=text,
        keywords=_extract_keywords(text),
    )


# ── Text extraction ────────────────────────────────────────────────────────────

def _extract_main_text(html: str) -> str:
    json_ld_text = _extract_json_ld_job(html)

    doc = Document(html)
    content_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(content_html, "lxml")
    page_text = "\n".join(soup.stripped_strings)

    merged = f"{json_ld_text}\n{page_text}".strip()
    merged = unescape(merged)
    merged = re.sub(r"\n{2,}", "\n", merged)
    return merged


def _extract_json_ld_job(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    collected: list[str] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for item in _iter_json_objects(data):
            if str(item.get("@type", "")).lower() == "jobposting":
                for key in ["title", "description", "qualifications",
                            "responsibilities", "skills"]:
                    value = item.get(key)
                    if isinstance(value, str):
                        collected.append(value)
    text = "\n".join(collected)
    return BeautifulSoup(text, "lxml").get_text("\n")


def _iter_json_objects(obj: object) -> Iterable[dict]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _iter_json_objects(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_json_objects(item)


# ── Metadata extraction ────────────────────────────────────────────────────────

def _extract_metadata(html: str, body_text: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "lxml")

    # 1. Try JSON-LD structured data first — most reliable
    title, company, location = _extract_json_ld_metadata(html)

    # 2. Try OG / meta tags
    if not title:
        og = soup.find("meta", property="og:title")
        title = og["content"].strip() if og and og.get("content") else ""

    # 3. Fall back to <title> tag — clean aggressively
    if not title and soup.title and soup.title.text:
        raw = soup.title.text.strip()
        # Strip everything after the first  |  –  —  separator
        raw = re.split(r"\s+[\|\-–—]\s+", raw)[0].strip()
        # Drop known noise phrases
        raw = _TITLE_NOISE.sub("", raw).strip()
        title = raw

    # 4. Try <h1> as final fallback
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Company from meta if not found in JSON-LD
    if not company:
        company = _search_first(body_text, [
            r"Company\s*[:\-]\s*([A-Z][A-Za-z0-9&.',\- ]{2,60})",
            r"Employer\s*[:\-]\s*([A-Z][A-Za-z0-9&.',\- ]{2,60})",
        ])

    # Location from meta if not found in JSON-LD
    if not location:
        location = _search_first(body_text, [
            r"Location\s*[:\-]\s*([A-Za-z0-9,/ ()-]{3,60})",
            r"([A-Za-z ]{3,30},\s*[A-Z]{2}(?:\s+\d{5})?)",
        ])

    return title[:120], company[:80], location[:80]


def _extract_json_ld_metadata(html: str) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for item in _iter_json_objects(data):
            if str(item.get("@type", "")).lower() == "jobposting":
                title    = item.get("title", "")
                company  = ""
                location = ""
                # Company from hiringOrganization
                org = item.get("hiringOrganization", {})
                if isinstance(org, dict):
                    company = org.get("name", "")
                # Location from jobLocation
                loc = item.get("jobLocation", {})
                if isinstance(loc, dict):
                    addr = loc.get("address", {})
                    if isinstance(addr, dict):
                        parts = [
                            addr.get("addressLocality", ""),
                            addr.get("addressRegion", ""),
                        ]
                        location = ", ".join(p for p in parts if p)
                if title:
                    return title, company, location
    return "", "", ""


def _search_first(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_keywords(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(kw for kw in COMMON_KEYWORDS if kw in lowered)
