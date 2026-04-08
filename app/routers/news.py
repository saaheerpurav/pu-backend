"""
News Router — reads from data/news.json (populated by scrape_news.py)
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/news", tags=["news"])

NEWS_FILE = Path(__file__).parent.parent.parent / "data" / "news.json"


def load_news() -> dict:
    if not NEWS_FILE.exists():
        return {"articles": [], "total": 0, "scraped_at": None}
    with open(NEWS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("")
def get_news(disaster_type: str = None):
    data = load_news()
    if not data["articles"]:
        raise HTTPException(
            status_code=404,
            detail="No news data found. Run: python scrape_news.py"
        )
    articles = data["articles"]
    if disaster_type:
        articles = [a for a in articles if a.get("disaster_type") == disaster_type]
    return {
        "articles": articles,
        "total": len(articles),
        "scraped_at": data.get("scraped_at"),
    }
