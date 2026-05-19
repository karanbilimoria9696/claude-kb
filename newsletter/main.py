import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

from database import get_articles_for_date, get_available_dates, init_db, save_articles
from scraper import fetch_candidates, pick_top


def _to_article(candidate: dict) -> dict:
    return {
        "title": candidate["title"],
        "source": candidate["source"],
        "original_url": candidate["url"],
        "company": None,
        "summary": candidate["summary"],
        "sales_opportunity": None,
        "saas_categories": None,
        "talking_points": None,
    }


def run_daily_job():
    """Fetch and save today's edition."""
    today = date.today()
    print(f"[job] Running daily edition for {today}")
    try:
        candidates = fetch_candidates(max_per_feed=20)
        top = pick_top(candidates, n=5)
        articles = [_to_article(c) for c in top]
        if articles:
            save_articles(articles, today)
            print(f"[job] Saved {len(articles)} articles for {today}")
        else:
            print("[job] No articles found — edition skipped")
    except Exception as e:
        print(f"[job] Error during daily job: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    scheduler = BackgroundScheduler(timezone="Australia/Sydney")
    # Run daily at 07:00 AEST
    scheduler.add_job(run_daily_job, "cron", hour=7, minute=0)
    scheduler.start()

    # If no articles exist for today, run immediately on startup
    if not get_articles_for_date(date.today()):
        print("[startup] No articles for today — running initial job now")
        run_daily_job()

    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _parse_talking_points(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return [raw]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, edition: str | None = None):
    available_dates = get_available_dates()

    if edition:
        try:
            selected_date = date.fromisoformat(edition)
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = available_dates[0] if available_dates else date.today()

    raw_articles = get_articles_for_date(selected_date)
    articles = []
    for a in raw_articles:
        articles.append({
            "id": a.id,
            "title": a.title,
            "source": a.source,
            "original_url": a.original_url,
            "company": a.company,
            "summary": a.summary,
            "sales_opportunity": a.sales_opportunity,
            "saas_categories": [c.strip() for c in (a.saas_categories or "").split(",") if c.strip()],
            "talking_points": _parse_talking_points(a.talking_points),
        })

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "articles": articles,
            "selected_date": selected_date,
            "available_dates": available_dates,
            "edition_label": selected_date.strftime("%-d %B %Y"),
        },
    )


@app.post("/refresh")
async def manual_refresh():
    """Manually trigger a refresh (useful for testing)."""
    run_daily_job()
    return {"status": "ok", "date": str(date.today())}
