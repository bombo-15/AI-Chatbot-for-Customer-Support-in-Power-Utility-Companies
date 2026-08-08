"""
Live scraper for ECG (Electricity Company of Ghana) outage data.
Fetches current outage and maintenance notices from https://www.ecg.com.gh
"""

import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://www.ecg.com.gh"

REGION_PATHS: dict[str, str] = {
    "Accra East":  "/index.php/en/regional-status/accra-east-region",
    "Accra West":  "/index.php/en/regional-status/accra-west-region",
    "Tema":        "/index.php/en/regional-status/tema-region",
    "Ashanti":     "/index.php/en/regional-status/ashanti-region",
    "Eastern":     "/index.php/en/regional-status/eastern-region",
    "Western":     "/index.php/en/regional-status/western-region",
    "Volta":       "/index.php/en/regional-status/volta-region",
    "Central":     "/index.php/en/regional-status/central-region",
}

STATUS_PATH = "/index.php/en/services/ecg-status/current-system-status"

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

_OUTAGE_KEYWORDS = {"outage", "maintenance", "emergency", "fault", "power", "interruption"}


# ── HTML fetching ─────────────────────────────────────────────────────────────

def _fetch(url: str) -> tuple[BeautifulSoup | None, str | None]:
    """Returns (soup, error_reason). error_reason is None on success, otherwise
    a short description (HTTP status or exception) — never silently swallowed."""
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; KaneaBot/1.0)"})
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser"), None
            return None, f"HTTP {resp.status_code}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_iso_date(text: str) -> str:
    """Extract ISO-formatted date from outage title text. Falls back to today."""
    m = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(january|february|march|april|may|june|july|august|september|october|november|december)"
        r"[,\s]+(\d{4})",
        text, re.IGNORECASE,
    )
    if m:
        day = int(m.group(1))
        month = _MONTH_MAP.get(m.group(2).lower(), 1)
        year = int(m.group(3))
        return f"{year}-{month:02d}-{day:02d}T00:00:00"
    return datetime.now().strftime("%Y-%m-%dT00:00:00")


def _classify(text: str) -> tuple[str, str]:
    """Returns (outage_type, status). type: unplanned|scheduled. status: active|scheduled."""
    lower = text.lower()
    if "planned maintenance" in lower or "scheduled" in lower:
        return "scheduled", "scheduled"
    if "emergency" in lower:
        return "unplanned", "active"
    return "unplanned", "active"


def _normalise_title(text: str) -> str:
    """Convert ALL-CAPS article titles to readable Title Case."""
    if text == text.upper():
        text = text.title()
    # Preserve common acronyms
    for acronym in ("Ecg", "Ht", "Kv", "Gridco", "Vra", "Purc"):
        text = text.replace(acronym, acronym.upper())
    return text.strip()


def _extract_cause(text: str) -> str:
    lower = text.lower()
    if "broken" in lower and ("pole" in lower or " ht " in lower):
        return "Broken high-tension (HT) pole"
    if "fault" in lower and "network" in lower:
        return "Network fault"
    feeder_m = re.search(r"fault on (?:the )?(.+?) feeder", lower)
    if feeder_m:
        return f"Fault on {feeder_m.group(1).title()} feeder"
    if "transformer" in lower:
        return "Transformer fault"
    if "gridco" in lower or "upstream" in lower:
        return "Upstream network issue (GRIDCo)"
    if "fire" in lower:
        return "Fire outbreak near equipment"
    if "gas" in lower:
        return "Gas supply challenge"
    if "emergency" in lower:
        return "Emergency maintenance"
    if "planned" in lower or "maintenance" in lower:
        return "Scheduled maintenance"
    return "Power outage"


def _region_from_href(href: str) -> str | None:
    lower = href.lower()
    for slug, label in [
        ("accra-east",  "Accra East"),
        ("accra-west",  "Accra West"),
        ("ashanti",     "Ashanti"),
        ("eastern",     "Eastern"),
        ("western",     "Western"),
        ("central",     "Central"),
        ("volta",       "Volta"),
        ("tema",        "Tema"),
    ]:
        if slug in lower:
            return label
    return None


def _is_outage_link(text: str, href: str) -> bool:
    if len(text) < 15:
        return False
    lower = text.lower()
    return any(kw in lower for kw in _OUTAGE_KEYWORDS)


def _links_to_outages(soup: BeautifulSoup, default_region: str) -> list[dict]:
    outages = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        text: str = a.get_text(separator=" ", strip=True)

        # Only process outage-status article links
        if "current-system-status" not in href and "regional-status" not in href:
            continue
        if not _is_outage_link(text, href):
            continue

        region = _region_from_href(href) or default_region
        otype, status = _classify(text)
        start = _parse_iso_date(text)
        cause = _extract_cause(text)
        title = _normalise_title(text)

        outages.append({
            "area":                    region,
            "type":                    otype,
            "start_time":              start,
            "estimated_restoration":   None,
            "affected_customers":      0,
            "status":                  status,
            "cause":                   cause,
            "source_title":            title[:300],
        })

    return outages


# ── Public API ────────────────────────────────────────────────────────────────

TOTAL_PAGES = len(REGION_PATHS) + 2  # homepage + status index + each regional page


def scrape_outages() -> tuple[list[dict], list[dict]]:
    """
    Scrape live outage data from the ECG homepage and all 8 regional status pages.
    Returns (outages, fetch_errors). fetch_errors has one entry per page that
    could not be retrieved — e.g. [{"url": ..., "reason": "HTTP 403"}] — so a
    site-wide block (WAF, downtime) is never mistaken for "no active outages".
    """
    all_outages: list[dict] = []
    seen: set[str] = set()
    fetch_errors: list[dict] = []

    def add_unique(entries: list[dict]) -> None:
        for entry in entries:
            key = entry["source_title"].lower()
            if key not in seen:
                seen.add(key)
                all_outages.append(entry)

    def fetch(url: str, region: str) -> None:
        soup, reason = _fetch(url)
        if soup is None:
            fetch_errors.append({"url": url, "reason": reason})
            return
        add_unique(_links_to_outages(soup, region))

    # 1. Homepage (contains the most recent status links)
    fetch(BASE_URL, "Ghana")

    # 2. Current status index page
    fetch(BASE_URL + STATUS_PATH, "Ghana")

    # 3. Each regional page
    for region, path in REGION_PATHS.items():
        fetch(BASE_URL + path, region)

    return all_outages, fetch_errors


def scrape_summary() -> dict:
    """Return a brief summary of what was scraped (for the admin endpoint)."""
    outages, fetch_errors = scrape_outages()
    regions_hit = list({o["area"] for o in outages})
    return {
        "total": len(outages),
        "regions": regions_hit,
        "scraped_at": datetime.now().isoformat(),
        "outages": outages,
        "fetch_errors": fetch_errors,
        "fully_blocked": len(fetch_errors) == TOTAL_PAGES,
    }
