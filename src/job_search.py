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
        "Obscura headless browser not found. Run once:\n"
        "    python setup.py\n"
        "Or download manually from:\n"
        "    https://github.com/h4ckf0r0day/obscura/releases\n"
        "Place obscura.exe and obscura-worker.exe in the bin/ directory."
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

    timeout: int = 15
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
            "--wait-until", "domcontentloaded",
            "--timeout", str(self.timeout),
            "--eval", _BING_EVAL_SCRIPT,
            "--quiet",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
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


# ── LinkedIn URL builder ──────────────────────────────────────────────────────

# LinkedIn f_E (experience level) mapping from our job_level values
_LINKEDIN_LEVEL_MAP: dict[str, str] = {
    "internship": "1",
    "entry":      "2",
    "junior":     "2",          # LinkedIn has no "junior" — map to Entry
    "mid":        "3,4",        # Associate + Mid-Senior
    "senior":     "4",          # Mid-Senior
    "lead":       "4,5",        # Mid-Senior + Director
    "manager":    "4,5",        # Mid-Senior + Director
}

# LinkedIn f_WT (work type) mapping
_LINKEDIN_WORK_MODE_MAP: dict[str, str] = {
    "onsite":  "1",
    "hybrid":  "2",
    "remote":  "3",
}

# LinkedIn geoId for major Indonesian cities + country
_LINKEDIN_GEO_IDS: dict[str, str] = {
    "indonesia":    "102478259",
    "jakarta":      "102749124",
    "bandung":      "104122966",
    "surabaya":     "104112802",
    "yogyakarta":   "104352555",
    "medan":        "104387822",
    "semarang":     "104555914",
    "bali":         "100510840",
    "tangerang":    "104555842",
    "bekasi":       "104555907",
    "depok":        "104555870",
    "bogor":        "102725340",
    "malang":       "104555886",
}


def _build_linkedin_url(filters: JobFilters) -> str:
    """Build a LinkedIn job search URL with all user filters as URL parameters.

    Uses LinkedIn's native filter parameters so the search is pre-filtered
    server-side, not just post-filtered on the result set.
    """
    from urllib.parse import urlencode

    params: dict[str, str] = {}

    # keywords — job title + skills as context
    keyword_parts: list[str] = []
    if filters.keyword.strip():
        keyword_parts.append(filters.keyword.strip())
    if filters.skills:
        keyword_parts.extend(filters.skills[:2])   # add up to 2 skills to keyword
    if keyword_parts:
        params["keywords"] = " ".join(keyword_parts)

    # Location — prefer geoId for precision, fallback to location string
    location_key = filters.location.strip().lower() if filters.location.strip() else "indonesia"
    geo_id = _LINKEDIN_GEO_IDS.get(location_key)
    if geo_id:
        params["geoId"] = geo_id
    elif filters.location.strip():
        params["location"] = filters.location.strip()
    else:
        # Default to Indonesia geoId when no location specified
        params["geoId"] = _LINKEDIN_GEO_IDS["indonesia"]

    # Experience level (f_E)
    level_key = filters.job_level.strip().lower()
    if level_key and level_key != "any":
        f_e = _LINKEDIN_LEVEL_MAP.get(level_key)
        if f_e:
            params["f_E"] = f_e

    # Work type (f_WT)
    mode_key = filters.work_mode.strip().lower()
    if mode_key and mode_key != "any":
        f_wt = _LINKEDIN_WORK_MODE_MAP.get(mode_key)
        if f_wt:
            params["f_WT"] = f_wt

    # Time posted (f_TPR) — use posted_after filter if set
    if filters.posted_after is not None:
        from datetime import date
        days_ago = (date.today() - filters.posted_after).days
        if days_ago <= 1:
            params["f_TPR"] = "r86400"
        elif days_ago <= 7:
            params["f_TPR"] = "r604800"
        elif days_ago <= 30:
            params["f_TPR"] = "r2592000"
        # > 30 days: omit — LinkedIn doesn't support longer windows
    else:
        # Default: past week so results are fresh
        params["f_TPR"] = "r604800"

    # Job type — always full-time by default (f_JT=F)
    params["f_JT"] = "F"

    return "https://id.linkedin.com/jobs/search?" + urlencode(params)


@dataclass(slots=True)
class LinkedInBackend:
    """Job search on LinkedIn via Obscura headless browser.

    Extracts real job listings: title, company, location, and apply URL.
    Requires ``obscura.exe`` in the project's ``bin/`` directory.

    Pass ``filters`` to the constructor so the LinkedIn URL is built with
    native filter parameters (f_E, f_WT, geoId, f_TPR) instead of relying
    on a plain keyword query that ignores level, work mode, and location.
    """

    timeout: int = 15
    filters: JobFilters | None = None
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search LinkedIn jobs and return structured results."""
        import subprocess

        elapsed = time.monotonic() - self._last_request
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        obscura_bin = _get_obscura_path()

        # Use native LinkedIn filter params when filters are available;
        # otherwise fall back to a plain keyword URL.
        if self.filters is not None:
            url = _build_linkedin_url(self.filters)
        else:
            encoded = quote_plus(query)
            url = (
                f"https://id.linkedin.com/jobs/search"
                f"?keywords={encoded}&f_JT=F&f_TPR=r604800"
                f"&geoId={_LINKEDIN_GEO_IDS['indonesia']}"
            )

        cmd = [
            obscura_bin,
            "fetch", url,
            "--stealth",
            "--wait-until", "domcontentloaded",
            "--timeout", str(self.timeout),
            "--eval", _LINKEDIN_EVAL_SCRIPT,
            "--quiet",
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
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


# ── Indeed backend ────────────────────────────────────────────────────────────

_INDEED_EVAL = """\
(function(){
    var r=[], seen={};
    document.querySelectorAll('.resultContent, .job_seen_beacon').forEach(function(c){
        var aEl=c.querySelector('h2.jobTitle a, a[data-jk]');
        if(!aEl) return;
        var t=aEl.querySelector('span[title]')?.getAttribute('title') || aEl.textContent?.trim()||'';
        var jk=aEl.getAttribute('data-jk')||aEl.href||'';
        if(!t||seen[t]) return; seen[t]=true;
        var co=c.querySelector('[data-testid="company-name"], .css-63koeb, .companyName')?.textContent?.trim()||'';
        var loc=c.querySelector('[data-testid="text-location"], .css-1p0sjhy, .companyLocation')?.textContent?.trim()||'';
        var link=aEl.href||'';
        r.push({title:t,company:co,location:loc,link:link});
    });
    return JSON.stringify(r);
})()"""


# ── Google Jobs backend ───────────────────────────────────────────────────────

_GOOGLE_JOBS_EVAL = """\
(function(){
    var r=[], seen={};
    document.querySelectorAll('.PUpOsf').forEach(function(c){
        var t=c.querySelector('.tNxQIb, h3')?.textContent?.trim()||'';
        if(!t||seen[t]) return; seen[t]=true;
        var co=c.querySelector('.wHYlTd, .vNEEBe')?.textContent?.trim()||'';
        var loc=c.querySelector('.r0wTwd, .Qk80Jf')?.textContent?.trim()||'';
        var link='';
        var p=c.closest('div');
        if(p){
            var aEl=p.querySelector('a[href*="http"]');
            if(aEl) link=aEl.href;
        }
        r.push({title:t,company:co,location:loc,link:link});
    });
    return JSON.stringify(r);
})()"""


@dataclass(slots=True)
class GoogleJobsBackend:
    """Job search on Google Jobs via Obscura.

    Uses Google's dedicated jobs vertical (udm=8).
    Prone to rate-limiting — use as supplementary source.
    """

    timeout: int = 300
    filters: JobFilters | None = None
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 15) -> list[dict[str, str]]:
        import json as json_mod
        import subprocess

        f = self.filters
        keyword = f.keyword.strip() if f and f.keyword.strip() else query
        location = f.location.strip() if f and f.location.strip() else ""
        full_query = f"{keyword} {location}".strip()

        url = f"https://www.google.com/search?q={quote_plus(full_query)}&udm=8&hl=en"

        # Rate limit aggressively
        elapsed = time.monotonic() - self._last_request
        if elapsed < 5.0:
            time.sleep(5.0 - elapsed)

        try:
            result = subprocess.run(
                [
                    _get_obscura_path(), "fetch", url,
                    "--stealth", "--wait-until", "networkidle2",
                    "--timeout", str(self.timeout),
                    "--eval", _GOOGLE_JOBS_EVAL, "--quiet",
                ],
                capture_output=True, text=True, timeout=self.timeout + 10,
            )
            self._last_request = time.monotonic()

            # Parse JSON output
            stdout = result.stdout
            json_start = stdout.find("[")
            if json_start < 0:
                return []
            raw = json_mod.loads(stdout[json_start:])

            results: list[dict[str, str]] = []
            for item in raw:
                if len(results) >= max_results:
                    break
                if not isinstance(item, dict) or not item.get("title"):
                    continue
                results.append({
                    "title": str(item.get("title", "")).strip(),
                    "company": str(item.get("company", "")).strip(),
                    "location": str(item.get("location", "")).strip(),
                    "snippet": "",
                    "url": str(item.get("link", "")).strip(),
                })
            self._last_request = time.monotonic()
            return results
        except Exception:
            return []  # Silently fail on Google rate-limit/CAPTCHA


# ── LLM-powered backend (BYOK) ───────────────────────────────────────────────


# Known values used to reconstruct filters from the free-text search query.
_KNOWN_JOB_LEVELS = {
    "internship", "entry", "junior", "mid", "senior", "lead", "manager",
}
_KNOWN_WORK_MODES = {"remote", "hybrid", "onsite"}
_KNOWN_LOCATIONS = {
    "jakarta", "bandung", "surabaya", "yogyakarta", "medan", "semarang",
    "bali", "tangerang", "bekasi", "depok", "bogor", "malang", "solo",
    "indonesia",
}


def _parse_llm_search_query(query: str) -> dict[str, str]:
    """Reconstruct keyword/location/level/mode/skills from a space-joined query.

    The orchestrator joins all filter values with spaces, so this parser
    extracts known categorical tokens and treats the remaining words as the
    job keyword (with any extra words passed as skills context).
    """
    tokens = query.lower().split()
    if not tokens:
        return {"keyword": "", "location": "", "job_level": "", "work_mode": "", "skills": ""}

    level = ""
    mode = ""
    location = ""
    remaining: list[str] = []

    for token in tokens:
        clean = re.sub(r"[^a-z]", "", token)
        if clean in _KNOWN_JOB_LEVELS and not level:
            level = clean
        elif clean in _KNOWN_WORK_MODES and not mode:
            mode = clean
        elif clean in _KNOWN_LOCATIONS and not location:
            location = clean.title() if clean != "indonesia" else "Indonesia"
        else:
            remaining.append(token)

    # The remaining words are the job keyword. Passing them all as the keyword
    # keeps the LLM query faithful to the user's original intent; the LLM can
    # infer relevant skills from the full phrase.
    keyword = " ".join(remaining)

    return {
        "keyword": keyword,
        "location": location,
        "job_level": level,
        "work_mode": mode,
        "skills": "",
    }


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

        parsed = _parse_llm_search_query(query)

        try:
            raw_results = ai_search_jobs(
                keyword=parsed["keyword"],
                location=parsed["location"],
                job_level=parsed["job_level"],
                work_mode=parsed["work_mode"],
                skills=parsed["skills"],
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


# ── Indeed Indonesia backend ─────────────────────────────────────────────────

@dataclass(slots=True)
class IndeedBackend:
    """Job search using Indeed Indonesia via Obscura."""

    timeout: int = 30
    filters: JobFilters | None = None
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 15) -> list[dict[str, str]]:
        obscura_bin = _get_obscura_path()
        f = self.filters
        keyword = quote_plus(f.keyword.strip() if f and f.keyword.strip() else query)
        location = quote_plus(f.location.strip() if f and f.location.strip() else "Indonesia")
        url = f"https://id.indeed.com/jobs?q={keyword}&l={location}&sort=date"

        # Rate limit
        elapsed = time.monotonic() - self._last_request
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        try:
            import subprocess

            result = subprocess.run(
                [
                    obscura_bin, "fetch", url,
                    "--stealth", "--wait-until", "networkidle2",
                    "--timeout", str(self.timeout),
                    "--eval", _INDEED_EVAL, "--quiet",
                ],
                capture_output=True, text=True, timeout=self.timeout + 10,
            )
            self._last_request = time.monotonic()
            return _parse_obscura_output(result.stdout, max_results)
        except Exception as exc:
            self._last_request = time.monotonic()
            raise RuntimeError(f"Indeed search failed: {exc}") from exc


# ── Glints Indonesia backend ──────────────────────────────────────────────────

_GLINTS_EVAL_SCRIPT = """\
(function(){
    var jobs = [];
    var cards = document.querySelectorAll(
        'a[aria-label^="Job card title:"], a.CompactOpportunityCardsc__JobCardTitleNoStyleAnchor-sc-dkg8my-12'
    );
    cards.forEach(function(a){
        var card    = a.closest('li, [class*="CompactOpportunity"]') || a.parentElement;
        var title   = a.getAttribute('aria-label') || a.textContent || '';
        title = title.replace(/^Job card title:\\s*/i, '').trim();
        var companyEl  = card ? (
            card.querySelector('a[class*="CompanyLinkResolver"], a[class*="CompanyLink"]') ||
            card.querySelector('[class*="CompanyName"]')
        ) : null;
        var locationEl = card ? card.querySelector('[class*="JobCardLocation"]') : null;
        var href = a.href || '';
        if (!href.startsWith('http')) href = 'https://glints.com' + href;
        if (!title) return;
        jobs.push({
            title:    title,
            company:  companyEl  ? companyEl.textContent.trim()  : '',
            location: locationEl ? locationEl.textContent.trim() : '',
            url:      href.split('?')[0]
        });
    });
    return JSON.stringify(jobs);
})()"""


@dataclass(slots=True)
class GlintsBackend:
    """Job search on Glints Indonesia via Obscura headless browser.

    URL: https://glints.com/id/opportunities/jobs/explore?keyword=<kw>&country=ID&locationName=<city>
    """

    timeout: int = 18
    filters: JobFilters | None = None
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search Glints Indonesia and return structured results."""
        import subprocess

        elapsed = time.monotonic() - self._last_request
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        obscura_bin = _get_obscura_path()
        f = self.filters
        keyword = quote_plus(f.keyword.strip() if f and f.keyword.strip() else query)
        location_name = (
            f.location.strip().title() if f and f.location.strip() else "Indonesia"
        )
        url = (
            f"https://glints.com/id/opportunities/jobs/explore"
            f"?keyword={keyword}&country=ID&locationName={quote_plus(location_name)}"
        )
        if f and f.job_level.lower() not in ("", "any"):
            lvl_map = {
                "internship": "INTERNSHIP", "entry": "FRESH_GRAD",
                "junior":     "LESS_THAN_A_YEAR", "mid": "ONE_TO_THREE_YEARS",
                "senior":     "THREE_TO_FIVE_YEARS", "lead": "MORE_THAN_FIVE_YEARS",
                "manager":    "MORE_THAN_FIVE_YEARS",
            }
            exp = lvl_map.get(f.job_level.lower(), "")
            if exp:
                url += f"&minYearsOfExperience={exp}"
        if f and f.work_mode.lower() == "remote":
            url += "&workArrangement=REMOTE"
        elif f and f.work_mode.lower() == "hybrid":
            url += "&workArrangement=HYBRID"

        try:
            result = subprocess.run(
                [
                    obscura_bin, "fetch", url,
                    "--stealth", "--wait-until", "networkidle2",
                    "--timeout", str(self.timeout),
                    "--eval", _GLINTS_EVAL_SCRIPT, "--quiet",
                ],
                capture_output=True, text=True, encoding="utf-8",
                timeout=self.timeout + 10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
        finally:
            self._last_request = time.monotonic()

        return _parse_glints_output(result.stdout, max_results)


def _parse_glints_output(stdout: str, max_results: int) -> list[dict[str, str]]:
    """Parse Glints eval JSON output into result dicts."""
    import json as json_mod

    json_start = stdout.find("[")
    if json_start < 0:
        return []
    try:
        raw = json_mod.loads(stdout[json_start:])
    except json_mod.JSONDecodeError:
        return []

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if len(results) >= max_results:
            break
        if not isinstance(item, dict) or not item.get("title"):
            continue
        url = str(item.get("url", "")).strip()
        if url in seen:
            continue
        seen.add(url)
        results.append({
            "title":    str(item.get("title",    "")).strip(),
            "company":  str(item.get("company",  "")).strip(),
            "location": str(item.get("location", "")).strip(),
            "snippet":  "",
            "url":      url,
        })
    return results


# ── Kalibrr Indonesia backend ─────────────────────────────────────────────────

_KALIBRR_EVAL_SCRIPT = """\
(function(){
    var nd = document.getElementById('__NEXT_DATA__');
    if (!nd) return JSON.stringify([]);
    try {
        var data = JSON.parse(nd.textContent);
        var jobs = (data.props && data.props.pageProps && data.props.pageProps.jobs)
                   ? data.props.pageProps.jobs : [];
        var results = [];
        for (var i = 0; i < jobs.length; i++) {
            var j = jobs[i];
            var loc = (j.locations && j.locations.length > 0)
                      ? j.locations[0].name || '' : '';
            var slug = j.slug || String(j.id);
            var code = (j.company && j.company.code) ? j.company.code : '';
            var url  = code
                ? 'https://www.kalibrr.id/id-ID/c/' + code + '/jobs/' + j.id + '/' + slug
                : 'https://www.kalibrr.id/id-ID/job-board/te/' + slug + '/o/' + j.id;
            results.push({
                title:    j.name || '',
                company:  (j.company && j.company.name) ? j.company.name : '',
                location: loc,
                url:      url
            });
        }
        return JSON.stringify(results);
    } catch(e) { return JSON.stringify([]); }
})()"""


@dataclass(slots=True)
class KalibrrBackend:
    """Job search on Kalibrr Indonesia via Obscura headless browser.

    Kalibrr is a Next.js SSR app — all job data is embedded in
    ``<script id="__NEXT_DATA__">`` as JSON, so no CSS selectors needed.
    """

    timeout: int = 18
    filters: JobFilters | None = None
    _last_request: float = field(default=0.0, init=False)

    def search(self, query: str, max_results: int = 20) -> list[dict[str, str]]:
        """Search Kalibrr Indonesia and return structured results."""
        import subprocess

        elapsed = time.monotonic() - self._last_request
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)

        obscura_bin = _get_obscura_path()
        f = self.filters
        keyword = f.keyword.strip().lower().replace(" ", "-") if f and f.keyword.strip() else query.lower().replace(" ", "-")
        location = (
            f.location.strip().lower().replace(" ", "-") if f and f.location.strip() else "indonesia"
        )
        url = f"https://www.kalibrr.id/id-ID/job-board/te/{quote_plus(keyword)}/lo/{quote_plus(location)}"

        try:
            result = subprocess.run(
                [
                    obscura_bin, "fetch", url,
                    "--stealth", "--wait-until", "domcontentloaded",
                    "--timeout", str(self.timeout),
                    "--eval", _KALIBRR_EVAL_SCRIPT, "--quiet",
                ],
                capture_output=True, text=True, encoding="utf-8",
                timeout=self.timeout + 10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
        finally:
            self._last_request = time.monotonic()

        return _parse_kalibrr_output(result.stdout, max_results, f)


def _parse_kalibrr_output(
    stdout: str, max_results: int, filters: JobFilters | None
) -> list[dict[str, str]]:
    """Parse Kalibrr __NEXT_DATA__ JSON output into result dicts."""
    import json as json_mod

    json_start = stdout.find("[")
    if json_start < 0:
        return []
    try:
        raw = json_mod.loads(stdout[json_start:])
    except json_mod.JSONDecodeError:
        return []

    results: list[dict[str, str]] = []
    for item in raw:
        if len(results) >= max_results:
            break
        if not isinstance(item, dict) or not item.get("title"):
            continue
        # Client-side filter by job_level / work_mode since Kalibrr URL params
        # for level/mode are handled by the URL filters above, but __NEXT_DATA__
        # may include extra entries — still apply loose post-filter
        title_lower = item.get("title", "").lower()
        if filters and filters.job_level.lower() not in ("", "any"):
            lvl = filters.job_level.lower()
            if lvl == "internship" and "intern" not in title_lower:
                pass  # keep — level can't be reliably inferred from title alone
        results.append({
            "title":    str(item.get("title",    "")).strip(),
            "company":  str(item.get("company",  "")).strip(),
            "location": str(item.get("location", "")).strip(),
            "snippet":  "",
            "url":      str(item.get("url",       "")).strip(),
        })
    return results


# ── Job search orchestration ─────────────────────────────────────────────────


# Domain patterns that indicate a job listing page
JOB_DOMAINS = {
    "linkedin.com/jobs",
    "linkedin.com/comm/jobs",
    "indeed.com",
    "id.indeed.com",
    "glints.com",
    "kalibrr.id",
    "kalibrr.com",
    "jobstreet.co.id",
    "jobstreet.com",
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

_LINKEDIN_DETAIL_EVAL = ('''(function(){var titleEl=document.querySelector("h1");var title=titleEl?titleEl.textContent.trim():"";var descEl=document.querySelector("[class*=description__text],[class*=show-more-less-html__markup]");var desc=descEl?descEl.textContent.trim():"";desc=desc.replace(/hapus teks|report this job|lapor lowongan ini/gi,"").trim();return JSON.stringify({title:title,description:desc});})()''')

_GLINTS_DETAIL_EVAL = ('''(function(){var h1=document.querySelector("h1");var title=h1?h1.textContent.trim():"";var descEl=document.querySelector("[class*=JobDescription],[class*=jobDescription]");var desc=descEl?descEl.textContent.trim():"";return JSON.stringify({title:title,description:desc});})()''')

_KALIBRR_DETAIL_EVAL = ('''(function(){var nd=document.getElementById("__NEXT_DATA__");if(!nd)return JSON.stringify({title:"",company:"",location:"",description:""});try{var data=JSON.parse(nd.textContent);var pp=(data&&data.props&&data.props.pageProps)?data.props.pageProps:{};var job=pp.job||pp.jobDetail||{};var company=(job.company&&job.company.name)?job.company.name:"";var location=(job.locations&&job.locations.length>0)?job.locations.map(function(l){return l.name;}).join(", "):"";return JSON.stringify({title:job.name||"",company:company,location:location,description:job.description?job.description.replace(/<[^>]+>/g," ").trim():""});}catch(e){return JSON.stringify({title:"",company:"",location:"",description:""});}})()''')


def _fetch_one_job_detail(url: str, obscura_bin: str) -> dict[str, str] | None:
    """Fetch a single job detail page via Obscura for any supported platform."""
    import subprocess

    url_lower = url.lower()
    if "linkedin.com/jobs/view/" in url_lower:
        eval_script = _LINKEDIN_DETAIL_EVAL
        wait_until = "domcontentloaded"
        timeout = "15"
    elif "glints.com" in url_lower and "/opportunities/" in url_lower:
        eval_script = _GLINTS_DETAIL_EVAL
        wait_until = "networkidle2"
        timeout = "22"
    elif "kalibrr.id" in url_lower and "/jobs/" in url_lower:
        eval_script = _KALIBRR_DETAIL_EVAL
        wait_until = "domcontentloaded"
        timeout = "15"
    elif "indeed.com" in url_lower or "id.indeed.com" in url_lower:
        return None
    else:
        return None

    try:
        result = subprocess.run(
            [
                obscura_bin, "fetch", url,
                "--stealth", "--wait-until", wait_until,
                "--timeout", timeout, "--eval", eval_script, "--quiet",
            ],
            capture_output=True, text=True, encoding="utf-8",
            timeout=int(timeout) + 10,
        )
        if result.returncode != 0:
            return None
        stdout = result.stdout
        json_start = stdout.find("{")
        if json_start < 0:
            return None
        import json as json_mod
        detail = json_mod.loads(stdout[json_start:])
        desc = detail.get("description", "")
        if not desc:
            return None
        return {
            "title": detail.get("title", ""),
            "company": detail.get("company", ""),
            "location": detail.get("location", ""),
            "snippet": desc[:500],
            "url": url,
        }
    except Exception:
        return None


def _fetch_job_details(urls: list[str], max_fetch: int = 5) -> list[dict[str, str]]:
    """Fetch full job descriptions from detail pages using Obscura in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    obscura_bin = _get_obscura_path()
    supported_prefixes = (
        "linkedin.com/jobs/view/",
        "glints.com",
        "kalibrr.id",
    )
    targets = [
        u for u in urls[:max_fetch]
        if any(p in u.lower() for p in supported_prefixes)
    ]
    results: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_fetch_one_job_detail, url, obscura_bin): url
            for url in targets
        }
        for future in as_completed(futures):
            detail = future.result()
            if detail is not None:
                results.append(detail)

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
        # ── Phase 1: Parallel Discovery — all platforms ───────────────
        # Run LinkedIn, Indeed, Glints, Kalibrr, and Bing concurrently.
        # Each runs in its own thread; failures are silently skipped.
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _search_platform(
            name: str, fn: Any, q: str, n: int
        ) -> tuple[str, list[dict[str, str]]]:
            try:
                return name, fn(q, n)
            except Exception:
                return name, []

        platforms: list[tuple[str, Any, str, int]] = [
            ("LinkedIn", LinkedInBackend(filters=filters).search,  query,                              max_results * 2),
            ("Indeed",   IndeedBackend(filters=filters).search,    query,                              max_results),
            ("Google",   GoogleJobsBackend(filters=filters).search, query,                             max_results),
            ("Glints",   GlintsBackend(filters=filters).search,    query,                              max_results),
            ("Kalibrr",  KalibrrBackend(filters=filters).search,   query,                              max_results),
            ("Bing",     ObscuraBackend().search,                   f"lowongan pekerjaan {query}",      max_results),
        ]

        with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
            futures = {
                executor.submit(_search_platform, name, fn, q, n): name
                for name, fn, q, n in platforms
            }
            for future in as_completed(futures):
                _, results = future.result()
                all_raw.extend(results)

    # ── Deduplicate by URL ───────────────────────────────────────────
    seen_urls: set[str] = set()
    unique: list[dict[str, str]] = []
    for r in all_raw:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(r)

    # ── Phase 2: Detail scraping (parallel, max 5) ───────────────────
    if fetch_details and unique:
        detail_urls = [r.get("url", "") for r in unique if r.get("url")]
        try:
            details = _fetch_job_details(detail_urls, max_fetch=5)
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
