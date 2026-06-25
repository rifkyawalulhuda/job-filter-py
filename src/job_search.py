"""AI-powered job vacancy search that integrates with the existing pipeline.

Searches across multiple job platforms using configurable search backends.
Results are returned as a normalized DataFrame ready for filtering and scoring.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote_plus

import pandas as pd

from src.data_loader import normalize_jobs
from src.filters import JobFilters

# ── Backend protocol ────────────────────────────────────────────────────────


class SearchBackend(Protocol):
    """Protocol for pluggable job search backends."""

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Return a list of raw search result dicts with title, snippet, url keys."""
        ...


# ── DuckDuckGo backend (free, no API key) ────────────────────────────────────


@dataclass(slots=True)
class DuckDuckGoBackend:
    """Job search using DuckDuckGo (HTML scraping, no API key required)."""

    timeout: int = 15
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search DuckDuckGo and return result dicts with title, snippet, url."""
        import requests as req

        # Rate limit: min 1.5s between requests
        elapsed = time.monotonic() - self._last_request
        if elapsed < 1.5:
            time.sleep(1.5 - elapsed)

        encoded = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            resp = req.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            html = resp.text
        except req.RequestException as exc:
            raise RuntimeError(
                f"DuckDuckGo search failed: {exc}"
            ) from exc
        finally:
            self._last_request = time.monotonic()

        return _parse_ddg_html(html, max_results)


def _parse_ddg_html(html: str, max_results: int) -> list[dict[str, str]]:
    """Extract search results from DuckDuckGo HTML response."""
    results: list[dict[str, str]] = []

    # Find result blocks: <a class="result__a"> for title/url,
    # <a class="result__snippet"> for snippet
    link_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (href, title) in enumerate(links):
        if i >= max_results:
            break
        snippet = _clean_html(snippets[i]) if i < len(snippets) else ""
        results.append(
            {
                "title": _clean_html(title),
                "snippet": snippet,
                "url": href,
            }
        )

    return results


def _clean_html(text: str) -> str:
    """Strip HTML tags and decode entities from a string."""
    # Remove HTML tags
    text = re.sub(r"<[^>]*>", " ", text)
    # Decode common entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#x27;", "'")
    text = text.replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── Google backend ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class GoogleBackend:
    """Job search using Google (HTML scraping, no API key required)."""

    timeout: int = 15
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search Google and return result dicts with title, snippet, url."""
        import requests as req

        elapsed = time.monotonic() - self._last_request
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        encoded = quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}&num={max_results}&hl=en"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            resp = req.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            html = resp.text
        except req.RequestException as exc:
            raise RuntimeError(f"Google search failed: {exc}") from exc
        finally:
            self._last_request = time.monotonic()

        return _parse_google_html(html, max_results)


def _parse_google_html(html: str, max_results: int) -> list[dict[str, str]]:
    """Extract search results from Google HTML response."""
    results: list[dict[str, str]] = []

    # Google wraps each result in various structures.
    # Try multiple extraction strategies.

    # Strategy 1: Look for <a> tags with href starting with http and
    # nearby text snippets
    link_pattern = re.compile(
        r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )
    snippet_pattern = re.compile(
        r'<div[^>]*class="[^"]*BNeawe[^"]*s3v9rd[^"]*AP7Wnd[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL,
    )

    # Find all potential links
    links = link_pattern.findall(html)
    snippets_raw = snippet_pattern.findall(html)
    snippets = [_clean_html(s) for s in snippets_raw]

    # Filter: skip Google internal links, very short titles
    seen_urls: set[str] = set()
    for href, title_raw in links:
        if len(results) >= max_results:
            break
        # Skip Google internal URLs
        if "google.com" in href or "google." in href.split("//")[-1].split("/")[0]:
            continue
        # Skip navigation, images, etc.
        if any(
            skip in href.lower()
            for skip in ("/maps", "/images", "/videos", "/news", "accounts.google")
        ):
            continue

        title = _clean_html(title_raw)
        if not title or len(title) < 4:
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        results.append(
            {
                "title": title,
                "snippet": snippets[len(results)] if len(results) < len(snippets) else "",
                "url": href,
            }
        )

    # Strategy 2: If strategy 1 got nothing, try simpler extraction
    if not results:
        results = _parse_search_results_fallback(html, max_results)

    return results


def _parse_search_results_fallback(
    html: str, max_results: int
) -> list[dict[str, str]]:
    """Fallback parser for search results when the main strategy fails."""
    results: list[dict[str, str]] = []

    # Find all <h3> headings (Google uses these for result titles)
    h3_pattern = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL | re.IGNORECASE)

    # Find all URLs
    url_pattern = re.compile(
        r'href="(https?://[^"]+)"', re.IGNORECASE
    )

    h3s = h3_pattern.findall(html)
    urls = url_pattern.findall(html)

    seen_urls: set[str] = set()
    for i, h3 in enumerate(h3s):
        if len(results) >= max_results:
            break
        title = _clean_html(h3)
        if not title or len(title) < 4:
            continue

        # Find the nearest URL that's not google.com
        url = ""
        for u in urls:
            if u in seen_urls:
                continue
            if "google." in u.split("//")[-1].split("/")[0]:
                continue
            if any(
                skip in u.lower()
                for skip in ("/maps", "/images", "/videos", "/news")
            ):
                continue
            url = u
            seen_urls.add(u)
            break

        results.append({"title": title, "snippet": "", "url": url})

    return results


# ── Yahoo backend (working on this machine) ──────────────────────────────────


@dataclass(slots=True)
class YahooBackend:
    """Job search using Yahoo (HTML scraping, no API key required)."""

    timeout: int = 15
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search Yahoo and return result dicts with title, snippet, url."""
        import requests as req

        elapsed = time.monotonic() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        encoded = quote_plus(query)
        url = f"https://search.yahoo.com/search?p={encoded}&n={max_results}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            resp = req.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            html = resp.text
        except req.RequestException as exc:
            raise RuntimeError(f"Yahoo search failed: {exc}") from exc
        finally:
            self._last_request = time.monotonic()

        return _parse_yahoo_html(html, max_results)


def _parse_yahoo_html(html: str, max_results: int) -> list[dict[str, str]]:
    """Extract search results from Yahoo HTML response."""
    results: list[dict[str, str]] = []

    # Extract titles from H3 tags
    title_pattern = re.compile(
        r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>.*?<span[^>]*>(.*?)</span>',
        re.DOTALL | re.IGNORECASE,
    )
    # Extract snippets
    snippet_pattern = re.compile(
        r'<p[^>]*class="[^"]*fc-dustygray[^"]*"[^>]*>(.*?)</p>',
        re.DOTALL,
    )
    # Extract redirect URLs and decode the RU parameter
    redirect_pattern = re.compile(
        r'/RU=(https?%3[aA][^"]+?)(?:/RK=|/RS=|")',
        re.IGNORECASE,
    )

    titles = title_pattern.findall(html)
    snippets_raw = snippet_pattern.findall(html)
    redirects = redirect_pattern.findall(html)

    # Decode and filter: keep only non-Yahoo external URLs
    from urllib.parse import unquote

    decoded_urls: list[str] = []
    for ru in redirects:
        url = unquote(ru)
        if "yahoo.com" not in url.lower() and "yimg.com" not in url.lower():
            decoded_urls.append(url)

    for i in range(min(len(titles), max_results)):
        title = _clean_html(titles[i])
        snippet = _clean_html(snippets_raw[i]) if i < len(snippets_raw) else ""
        url = decoded_urls[i] if i < len(decoded_urls) else ""

        if not title or len(title) < 4:
            continue

        results.append({"title": title, "snippet": snippet, "url": url})

    return results


# ── Obscura backend (headless browser, recommended) ──────────────────────────


# Path to the obscura binary, relative to project root
_OBSCURA_BIN = None


def _get_obscura_path() -> str:
    """Locate the obscura binary shipped with the project."""
    global _OBSCURA_BIN
    if _OBSCURA_BIN:
        return _OBSCURA_BIN

    candidates = [
        Path(__file__).resolve().parent.parent / "bin" / "obscura.exe",
        Path(__file__).resolve().parent.parent / "bin" / "obscura",
        Path("bin/obscura.exe"),
        Path("bin/obscura"),
    ]
    for candidate in candidates:
        if candidate.exists():
            _OBSCURA_BIN = str(candidate)
            return _OBSCURA_BIN

    raise RuntimeError(
        "Obscura binary not found. Download it from "
        "https://github.com/h4ckf0r0day/obscura/releases "
        "and place obscura.exe in the bin/ directory."
    )


def _decode_bing_url(redirect_url: str) -> str:
    """Decode a Bing redirect URL's ``u=`` parameter into the real URL."""
    import base64

    match = re.search(r"[?&]u=(a1[a-zA-Z0-9_%+\-/]+)", redirect_url)
    if not match:
        return redirect_url

    encoded = match.group(1)
    # Strip Bing's "a1" prefix, replace URL-safe chars
    b64_data = encoded[2:].replace("_", "/").replace("-", "+")
    # Add padding
    padding = (4 - len(b64_data) % 4) % 4
    b64_data += "=" * padding

    try:
        decoded = base64.b64decode(b64_data).decode("utf-8", errors="replace")
        # Skip any leading non-URL bytes
        http_pos = decoded.find("http")
        if http_pos >= 0:
            return decoded[http_pos:]
        return decoded
    except Exception:
        return redirect_url


_BING_EVAL_SCRIPT = """\
(function(){
    var results = [];
    var items = document.querySelectorAll('li.b_algo');
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var title = (item.querySelector('h2') || {}).textContent || '';
        var link = (item.querySelector('h2 a') || {}).href || '';
        var snippet = '';
        var capP = item.querySelector('.b_caption p');
        if (capP) snippet = capP.textContent || '';
        if (!snippet) {
            var capSpan = item.querySelector('.b_caption .b_lineclamp2');
            if (capSpan) snippet = capSpan.textContent || '';
        }
        results.push({
            title: title.trim(),
            link: link,
            snippet: snippet.trim()
        });
    }
    return JSON.stringify(results);
})()"""


@dataclass(slots=True)
class ObscuraBackend:
    """Job search using Obscura headless browser (Bing search engine).

    Requires ``obscura.exe`` in the project's ``bin/`` directory.
    Downloads: https://github.com/h4ckf0r0day/obscura/releases
    """

    timeout: int = 25
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search Bing via Obscura and return structured results."""
        import subprocess

        elapsed = time.monotonic() - self._last_request
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        obscura_bin = _get_obscura_path()
        encoded = quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded}&count={max_results}"

        cmd = [
            obscura_bin,
            "fetch", url,
            "--stealth",
            "--wait-until", "networkidle2",
            "--timeout", str(self.timeout),
            "--eval", _BING_EVAL_SCRIPT,
            "--quiet",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 10,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Obscura search timed out. Try again.")
        except FileNotFoundError:
            raise RuntimeError(
                f"Obscura binary not found at: {obscura_bin}. "
                "Download from https://github.com/h4ckf0r0day/obscura/releases"
            )
        finally:
            self._last_request = time.monotonic()

        if result.returncode != 0:
            error = result.stderr.strip() or "unknown error"
            raise RuntimeError(f"Obscura search failed: {error}")

        return _parse_obscura_output(result.stdout, max_results)


def _parse_obscura_output(stdout: str, max_results: int) -> list[dict[str, str]]:
    """Parse Obscura's JSON output into search result dicts."""
    import json as json_mod

    # Obscura output may have info lines before the JSON; find the JSON array
    json_start = stdout.find("[{")
    if json_start < 0:
        json_start = stdout.find("[")
        if json_start < 0:
            return []

    try:
        raw_results = json_mod.loads(stdout[json_start:])
    except json_mod.JSONDecodeError:
        return []

    results: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        if len(results) >= max_results:
            break

        raw_url = str(item.get("link", ""))
        real_url = _decode_bing_url(raw_url) if "bing.com/ck/" in raw_url else raw_url

        results.append(
            {
                "title": str(item.get("title", "")).strip(),
                "snippet": str(item.get("snippet", "")).strip(),
                "url": real_url,
            }
        )

    return results


# ── LinkedIn backend (real job listings via Obscura) ─────────────────────────

_LINKEDIN_EVAL_SCRIPT = """\
(function(){
    var results = [];
    var cards = document.querySelectorAll(
        '.job-search-card, .job-card-container, .base-card, ' +
        '.jobs-search-results__list-item, li.jobs-search-results__list-item'
    );
    for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var title = (
            card.querySelector('.base-search-card__title, .job-search-card__title') ||
            card.querySelector('a[data-tracking-control-name="public_jobs_jserp-result"] span') ||
            card.querySelector('.sr-only') ||
            {}
        ).textContent || '';
        var company = (
            card.querySelector('.base-search-card__subtitle, .job-search-card__subtitle') ||
            card.querySelector('.job-search-card__company-name') ||
            {}
        ).textContent || '';
        var location = (
            card.querySelector('.job-search-card__location') ||
            card.querySelector('.base-search-card__metadata span') ||
            {}
        ).textContent || '';
        var link = (
            card.querySelector('a.base-card__full-link, a.job-search-card__link') ||
            card.querySelector('a[href*=\"/jobs/view/\"]') ||
            {}
        ).href || '';
        results.push({
            title: title.trim(),
            company: company.trim(),
            location: location.trim(),
            link: link
        });
    }
    return JSON.stringify(results);
})()"""


@dataclass(slots=True)
class LinkedInBackend:
    """Job search on LinkedIn via Obscura headless browser.

    Extracts real job listings: title, company, location, and apply URL.
    Requires ``obscura.exe`` in the project's ``bin/`` directory.
    """

    timeout: int = 25
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search LinkedIn jobs and return structured results."""
        import subprocess

        elapsed = time.monotonic() - self._last_request
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        obscura_bin = _get_obscura_path()
        encoded = quote_plus(query)
        # Use Indonesian LinkedIn domain for local results
        url = (
            f"https://id.linkedin.com/jobs/search"
            f"?keywords={encoded}&f_JT=F&f_TPR=r604800"
        )

        cmd = [
            obscura_bin,
            "fetch", url,
            "--stealth",
            "--wait-until", "networkidle2",
            "--timeout", str(self.timeout),
            "--eval", _LINKEDIN_EVAL_SCRIPT,
            "--quiet",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 10,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("LinkedIn search timed out. Try again.")
        except FileNotFoundError:
            raise RuntimeError(
                f"Obscura binary not found at: {obscura_bin}. "
                "Download from https://github.com/h4ckf0r0day/obscura/releases"
            )
        finally:
            self._last_request = time.monotonic()

        if result.returncode != 0:
            error = result.stderr.strip() or "unknown error"
            raise RuntimeError(f"LinkedIn search failed: {error}")

        return _parse_linkedin_output(result.stdout, max_results)


def _parse_linkedin_output(stdout: str, max_results: int) -> list[dict[str, str]]:
    """Parse LinkedIn job search JSON into search result dicts."""
    import json as json_mod

    json_start = stdout.find("[{")
    if json_start < 0:
        return []

    try:
        raw_results = json_mod.loads(stdout[json_start:])
    except json_mod.JSONDecodeError:
        return []

    results: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        if len(results) >= max_results:
            break

        title = str(item.get("title", "")).strip()
        company = str(item.get("company", "")).strip()
        location = str(item.get("location", "")).strip()
        link = str(item.get("link", "")).strip()

        # Build a rich description from the structured data
        description_parts = [title]
        if company:
            description_parts.append(f"at {company}")
        if location:
            description_parts.append(f"in {location}")

        results.append(
            {
                "title": title,
                "company": company,
                "location": location,
                "snippet": f"{title} at {company} in {location}" if company else title,
                "url": link,
            }
        )

    return results


# ── LLM-powered backend (BYOK) ───────────────────────────────────────────────


@dataclass(slots=True)
class LLMSearchBackend:
    """AI-powered job search using user's LLM (BYOK).

    Uses the configured LLM to search for job listings and return structured data.
    Falls back to LinkedIn scraping if LLM is not configured.
    """

    timeout: int = 60
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search for jobs via LLM and return structured results."""
        from src.llm import (
            LLMConfig,
            ai_search_jobs,
            load_llm_config,
        )

        elapsed = time.monotonic() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        try:
            config = load_llm_config()
            if not config.is_configured:
                raise ValueError("LLM not configured")
        except Exception:
            raise RuntimeError(
                "LLM is not configured. Set your API key in the BYOK panel."
            )
        finally:
            self._last_request = time.monotonic()

        # Parse query into filter-like components
        parts = query.split()
        keyword = parts[0] if parts else query
        location = ""
        job_level = ""
        skills = ""

        # Simple heuristic: 2nd word might be location
        if len(parts) > 1 and parts[1][0].isupper():
            location = parts[1]
        if len(parts) > 2:
            skills = " ".join(parts[2:5])

        try:
            raw_results = ai_search_jobs(
                keyword=keyword,
                location=location,
                job_level=job_level,
                skills=skills,
                max_results=max_results,
                config=config,
            )
        except Exception as exc:
            raise RuntimeError(f"LLM search failed: {exc}") from exc

        # Convert to standard format
        results: list[dict[str, str]] = []
        for item in raw_results:
            results.append(
                {
                    "title": str(item.get("title", "")).strip(),
                    "company": str(item.get("company", "")).strip(),
                    "location": str(item.get("location", "")).strip(),
                    "snippet": str(item.get("snippet", "")).strip(),
                    "url": str(item.get("apply_url", "")).strip(),
                }
            )

        return results


# ── Job search orchestration ─────────────────────────────────────────────────


# Domain patterns that indicate a job listing page
JOB_DOMAINS = {
    "linkedin.com/jobs",
    "linkedin.com/comm/jobs",
    "indeed.com",
    "glints.com",
    "jobstreet.co.id",
    "jobstreet.com",
    "kalibrr.com",
    "glassdoor.com",
    "seek.com.au",
    "monster.com",
    "ziprecruiter.com",
    "karir.com",
    "jobsdb.com",
}

JOB_TITLE_PATTERNS = (
    r"(?i)(senior|junior|lead|staff|principal|mid|entry|internship)\s+",
    r"(?i)(engineer|developer|analyst|designer|manager|scientist|architect|"
    r"consultant|specialist|administrator|coordinator|director|associate)",
)

COMPANY_INDICATORS = (
    r"(?i)(?:at|with|for|di)\s+([A-Z][a-zA-Z0-9\s&.,]+?)(?:\s*[-–—|]|\s*$|\s+in\s|\s+is\s)",
    r"(?i)^([A-Z][a-zA-Z0-9\s&.,]+?)\s+[-–—|]\s+",
    r"(?i)([A-Z][a-zA-Z0-9\s&.,]+?)\s+is\s+(?:hiring|looking)",
)


def _is_job_listing(result: dict[str, str]) -> bool:
    """Check if a search result looks like a job listing."""
    url = result.get("url", "").lower()
    title = result.get("title", "").lower()
    snippet = result.get("snippet", "").lower()
    combined = f"{title} {snippet}"

    # Check if URL is from a known job platform
    if any(domain in url for domain in JOB_DOMAINS):
        return True

    # Check for job-related keywords
    job_keywords = (
        "hiring", "apply", "vacancy", "lowongan", "job", "career",
        "position", "opportunity", "opening", "recruitment", "rekrutmen",
        "full-time", "part-time", "remote", "hybrid",
    )
    if any(kw in combined for kw in job_keywords):
        # Avoid false positives: news articles about jobs
        false_positives = ("phishing", "scam", "news", "report")
        if not any(fp in combined for fp in false_positives):
            return True

    return False


def _extract_job_title(title: str, snippet: str) -> str:
    """Extract a clean job title from search result text."""
    combined = f"{title} {snippet}"

    # Try to find a job title pattern
    patterns = [
        # "Senior Python Developer" type patterns
        r"(?i)(?:^|\s)((?:senior|junior|lead|staff|principal|mid|entry|internship)\s+"
        r"(?:\w+\s+)?(?:software\s+|web\s+|data\s+|devops\s+|cloud\s+|"
        r"full\s*stack\s+|frontend\s+|backend\s+|mobile\s+|ui\s*/\s*ux\s+)?"
        r"(?:engineer|developer|analyst|designer|manager|scientist|"
        r"architect|consultant|specialist|administrator|coordinator|"
        r"director|associate|programmer))\b",
        # Standard role patterns
        r"(?i)(?:^|\s)((?:software\s+|web\s+|data\s+|devops\s+|cloud\s+|"
        r"full\s*stack\s+|frontend\s+|backend\s+|mobile\s+|ui\s*/\s*ux\s+)?"
        r"(?:engineer|developer|analyst|designer|manager|scientist|"
        r"architect|programmer))\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return match.group(1).strip()

    # Fallback: use the first part of the title
    cleaned = re.sub(r"\s*[-–—|]\s*.*$", "", title)
    cleaned = re.sub(r"\s+(at|di)\s+.*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or title.strip()


def _extract_company(title: str, snippet: str) -> str:
    """Extract company name from search result text."""
    combined = f"{title} {snippet}"

    patterns = [
        r"(?i)\b(?:at|with|for|di)\s+((?-i:[A-Z])[A-Za-z0-9\s&.,]{2,30}?)(?:\s*[-–—|]|\s*$|\s+in\s|\s+is\s|\s+\d)",
        r"(?i)((?-i:[A-Z])[A-Za-z0-9\s&.,]{2,30}?)\s+is\s+(?:hiring|looking)",
        r"(?i)^[^-–—|]*?\s*[-–—|]\s*((?-i:[A-Z])[A-Za-z0-9\s&.,]{2,30}?)\s",
        r"(?i)\b(?:at|with|for|di)\s+((?-i:[A-Z])[A-Za-z0-9\s&.,]{2,30}?)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            company = match.group(1).strip()
            # Filter out non-company matches
            if company.lower() not in {
                "the", "a", "an", "this", "that", "your", "our",
                "full", "part", "time", "remote", "hybrid", "onsite",
            }:
                return company.strip(" .,;")

    return ""


def _extract_location(title: str, snippet: str) -> str:
    """Extract location from search result text."""
    combined = f"{title} {snippet}"

    # Common Indonesian and international location patterns
    patterns = [
        r"(?i)(?:in|at|di|located in|location:?)\s+([A-Z][A-Za-z\s,]{2,40}?)(?:\s*[-–—|]|\s*$)",
        r"(?i)(Jakarta|Bandung|Surabaya|Yogyakarta|Medan|Semarang|Bali|"
        r"Tangerang|Bekasi|Depok|Bogor|Malang|Solo)(?:\s*(?:Selatan|Utara|Timur|Barat|Pusat))?",
    ]

    for pattern in patterns:
        match = re.search(pattern, combined)
        if match:
            return match.group(1).strip()

    return ""


def _result_to_row(result: dict[str, str]) -> dict[str, object]:
    """Convert a single search result into a job row dict."""
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    url = result.get("url", "")
    # Use backend-provided company/location if available (LinkedIn)
    backend_company = result.get("company", "")
    backend_location = result.get("location", "")

    return {
        "job_title": _extract_job_title(title, snippet),
        "company": backend_company or _extract_company(title, snippet),
        "location": backend_location or _extract_location(title, snippet),
        "work_mode": "",
        "job_level": "",
        "salary_min": "",
        "salary_max": "",
        "currency": "",
        "skills": "",
        "posted_date": "",
        "job_type": "",
        "apply_url": url,
        "description": f"{title}\n{snippet}".strip(),
    }


# ── Detail page scraping ─────────────────────────────────────────────────────

_LINKEDIN_DETAIL_EVAL = """\
(function(){
    var title = document.querySelector('.top-card-layout__title, h1')?.textContent?.trim() || '';
    var company = document.querySelector('.topcard__org-name-link, [class*="company"] a, .topcard__flavor a')?.textContent?.trim() || '';
    var loc = document.querySelector('.topcard__flavor--bullet, [class*="location"] span')?.textContent?.trim() || '';
    var desc = document.querySelector('.description__text, .show-more-less-html__markup')?.textContent?.trim() || '';
    // Filter out UI text like "Hapus teks", "Report this job"
    desc = desc.replace(/hapus teks|report this job|lapor lowongan ini/gi, '').trim();
    loc = loc.replace(/hapus teks|report this job/gi, '').trim();
    return JSON.stringify({title:title, company:company, location:loc, description:desc});
})()"""


def _fetch_job_details(urls: list[str], max_fetch: int = 15) -> list[dict[str, str]]:
    """Fetch full job descriptions from detail pages using Obscura."""
    import subprocess

    obscura_bin = _get_obscura_path()
    results: list[dict[str, str]] = []

    for url in urls[:max_fetch]:
        if "linkedin.com/jobs/view/" not in url:
            continue
        try:
            result = subprocess.run(
                [
                    obscura_bin, "fetch", url,
                    "--stealth", "--wait-until", "networkidle2",
                    "--timeout", "20", "--eval", _LINKEDIN_DETAIL_EVAL, "--quiet",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                continue
            stdout = result.stdout
            json_start = stdout.find("{")
            if json_start < 0:
                continue
            import json as json_mod
            detail = json_mod.loads(stdout[json_start:])
            desc = detail.get("description", "")
            if desc:
                results.append({
                    "title": detail.get("title", ""),
                    "company": detail.get("company", ""),
                    "location": detail.get("location", ""),
                    "snippet": desc[:300],
                    "url": url,
                })
            time.sleep(1.5)  # Rate limit between fetches
        except Exception:
            continue

    return results


# ── Multi-platform orchestrator ──────────────────────────────────────────────


def search_jobs(
    filters: JobFilters,
    max_results: int = 25,
    backend: SearchBackend | None = None,
    fetch_details: bool = True,
) -> pd.DataFrame:
    """Search for job vacancies across multiple platforms.

    Phase 1: Discover job listings from LinkedIn + Bing search.
    Phase 2: Scrape detail pages for full job descriptions.
    Phase 3: Merge, deduplicate, and normalize.

    Parameters
    ----------
    filters:
        The active filter values used to build the search query.
    max_results:
        Maximum number of job results to return (default 25).
    backend:
        Optional backend override. Defaults to multi-platform orchestrator.
    fetch_details:
        Whether to scrape detail pages for full descriptions (default True).

    Returns
    -------
    pandas.DataFrame
        A normalized DataFrame of job vacancies.

    Raises
    ------
    ValueError
        If no useful search query can be built or no results found.
    """
    query = _build_search_query(filters)
    if not query.strip():
        raise ValueError(
            "Please provide at least a keyword or location to search for jobs."
        )

    all_raw: list[dict[str, str]] = []

    # If a custom backend is provided, use it directly (for tests/mock)
    if backend is not None:
        try:
            raw_results = backend.search(query, max_results=max_results * 2)
            all_raw.extend(raw_results)
        except Exception as exc:
            raise RuntimeError(
                f"Job search failed: {exc}"
            ) from exc
    else:
        # ── Phase 1: Discovery — LinkedIn ─────────────────────────────
        try:
            linkedin = LinkedInBackend()
            linkedin_results = linkedin.search(query, max_results=max_results * 2)
            all_raw.extend(linkedin_results)
        except Exception:
            pass

        # ── Phase 1b: Discovery — Bing (supplementary) ───────────────
        if len(all_raw) < max_results:
            try:
                bing_query = f"lowongan pekerjaan {query}"
                bing = ObscuraBackend()
                bing_results = bing.search(bing_query, max_results=max_results)
                all_raw.extend(bing_results)
            except Exception:
                pass

    # ── Deduplicate by URL ───────────────────────────────────────────
    seen_urls: set[str] = set()
    unique: list[dict[str, str]] = []
    for r in all_raw:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(r)

    # ── Phase 2: Detail scraping ─────────────────────────────────────
    if fetch_details and unique:
        detail_urls = [r.get("url", "") for r in unique if r.get("url")]
        try:
            details = _fetch_job_details(detail_urls, max_fetch=min(15, max_results))
            # Merge details into unique results (replace matching URLs)
            detail_map = {d["url"]: d for d in details}
            for r in unique:
                if r.get("url") in detail_map:
                    d = detail_map[r["url"]]
                    if d.get("snippet"):
                        r["snippet"] = d["snippet"]
                    if d.get("company") and not r.get("company"):
                        r["company"] = d["company"]
                    if d.get("location") and not r.get("location"):
                        r["location"] = d["location"]
        except Exception:
            pass

    # ── Convert to rows ──────────────────────────────────────────────
    job_rows: list[dict[str, object]] = []
    for result in unique:
        if len(job_rows) >= max_results:
            break
        if _is_job_listing(result):
            job_rows.append(_result_to_row(result))

    if not job_rows:
        raise ValueError(
            "No job listings found for the given search criteria. "
            "Try adjusting your keyword or location filters."
        )

    df = pd.DataFrame(job_rows)
    return normalize_jobs(df)


def _build_search_query(filters: JobFilters) -> str:
    """Build an optimized search query from user filters."""
    parts: list[str] = []

    # Keyword / job title — most important
    if filters.keyword.strip():
        parts.append(filters.keyword.strip())

    # Location
    if filters.location.strip():
        parts.append(filters.location.strip())

    # Job level
    if filters.job_level.strip() and filters.job_level.lower() != "any":
        parts.append(filters.job_level.strip())

    # Work mode
    if filters.work_mode.strip() and filters.work_mode.lower() != "any":
        parts.append(filters.work_mode.strip())

    # Skills as additional context
    if filters.skills:
        parts.append(" ".join(filters.skills[:3]))

    if not parts:
        return ""

    # Clean query for LinkedIn — no job indicators needed, it's a job platform
    return " ".join(parts)
