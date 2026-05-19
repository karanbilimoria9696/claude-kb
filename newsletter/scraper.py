import feedparser
import httpx
import re
from datetime import datetime, timezone

# ANZ-focused IT/SaaS RSS feeds
FEEDS = [
    ("iTnews", "https://www.itnews.com.au/rss/news"),
    ("CRN Australia", "https://www.crn.com.au/rss/"),
    ("ARN", "https://www.arnnet.com.au/rss/"),
    ("Computerworld AU", "https://www.computerworld.com/index.rss"),
    ("ZDNet", "https://www.zdnet.com/news/rss.xml"),
]

# Keywords that signal ANZ relevance
ANZ_KEYWORDS = [
    "australia", "australian", "new zealand", "auckland", "sydney", "melbourne",
    "brisbane", "perth", "adelaide", "canberra", "queensland", "victoria",
    "anz", "apac", "asia pacific", "woolworths", "coles", "telstra", "optus",
    "commonwealth bank", "westpac", "anz bank", "nab", "macquarie", "qantas",
    "bhp", "rio tinto", "wesfarmers", "bunnings", "afterpay", "canva", "atlassian",
    "seek", "realestate.com", "domain", "tabcorp", "nrma", "suncorp",
]

# Keywords that indicate SaaS/IT relevance
SAAS_KEYWORDS = [
    "cloud", "saas", "software", "digital transformation", "ai", "artificial intelligence",
    "cybersecurity", "security", "data", "erp", "crm", "infrastructure", "platform",
    "migration", "implementation", "enterprise", "technology", "microsoft", "salesforce",
    "servicenow", "workday", "sap", "oracle", "aws", "azure", "google cloud",
    "automation", "analytics", "devops", "iot", "api", "integration",
]


def _score_article(title: str, summary: str) -> tuple[int, bool]:
    """Return (score, is_anz). Higher score = more relevant."""
    text = (title + " " + summary).lower()

    anz_hits = sum(1 for kw in ANZ_KEYWORDS if kw in text)
    saas_hits = sum(1 for kw in SAAS_KEYWORDS if kw in text)

    # Must have at least one SAAS keyword to be worth covering
    if saas_hits == 0:
        return 0, False

    score = saas_hits * 2 + anz_hits * 3
    is_anz = anz_hits > 0
    return score, is_anz


def _clean_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:2000]


def fetch_candidates(max_per_feed: int = 15) -> list[dict]:
    candidates = []

    for source_name, feed_url in FEEDS:
        try:
            # feedparser is synchronous; use it directly
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                raw_summary = entry.get("summary", "") or entry.get("description", "")
                summary = _clean_html(raw_summary)
                url = entry.get("link", "")

                score, is_anz = _score_article(title, summary)
                if score == 0:
                    continue

                candidates.append({
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "source": source_name,
                    "score": score,
                    "is_anz": is_anz,
                })
        except Exception as e:
            print(f"[scraper] Failed to fetch {source_name}: {e}")

    # Sort: ANZ articles first, then by score
    candidates.sort(key=lambda x: (not x["is_anz"], -x["score"]))
    return candidates


def pick_top(candidates: list[dict], n: int = 5) -> list[dict]:
    """Deduplicate by title similarity and return top n."""
    seen_titles: set[str] = set()
    picked = []
    for c in candidates:
        # Simple dedupe: lowercase title words
        key = " ".join(sorted(c["title"].lower().split()))
        if key in seen_titles:
            continue
        seen_titles.add(key)
        picked.append(c)
        if len(picked) >= n:
            break
    return picked
