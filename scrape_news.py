"""
Run this script manually to scrape news and save to data/news.json.
The API reads from that file — no scraping happens at runtime.

Usage:
    python scrape_news.py
"""

import json
import time
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_FILE = Path(__file__).parent / "data" / "news.json"

SEARCH_QUERIES = [
    "flood India",
    "earthquake India",
    "cyclone India",
    "landslide India",
    "disaster relief India",
    "wildfire India",
]

DISASTER_KEYWORDS = [
    "flood", "earthquake", "cyclone", "landslide", "disaster",
    "wildfire", "fire", "tsunami", "relief", "rescue", "evacuate",
    "storm", "drought", "mudslide", "emergency", "tremor",
]

DISASTER_TYPE_MAP = {
    "flood": "flood", "flooding": "flood", "waterlog": "flood",
    "earthquake": "earthquake", "tremor": "earthquake", "quake": "earthquake",
    "fire": "fire", "wildfire": "fire", "blaze": "fire",
    "cyclone": "other", "storm": "other", "tsunami": "other",
    "landslide": "landslide", "mudslide": "landslide",
}


def detect_disaster_type(text: str) -> str:
    text = text.lower()
    for kw, dtype in DISASTER_TYPE_MAP.items():
        if kw in text:
            return dtype
    return "other"


def is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in DISASTER_KEYWORDS)


def scrape_query(query: str) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:5]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()
            published = entry.get("published", "")

            if not is_relevant(title, summary):
                continue

            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                source = parts[1].strip()

            combined_text = title + " " + summary
            articles.append({
                "title": title,
                "source": source,
                "url": link,
                "summary": summary[:400] if summary else "",
                "published": published,
                "disaster_type": detect_disaster_type(combined_text),
                "query": query,
            })
        return articles
    except Exception as e:
        print(f"  [!] Failed '{query}': {e}")
        return []


def run():
    print("ResQNet News Scraper")
    print("=" * 40)

    all_articles = []
    seen_titles = set()

    for query in SEARCH_QUERIES:
        print(f"Scraping: {query}...")
        articles = scrape_query(query)
        for a in articles:
            if a["title"] not in seen_titles:
                seen_titles.add(a["title"])
                all_articles.append(a)
                print(f"  + {a['title'][:65]}")
        time.sleep(0.5)

    output = {
        "articles": all_articles,
        "total": len(all_articles),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print()
    print(f"Done. {len(all_articles)} articles saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
