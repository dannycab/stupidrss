# Compatibility shim for Python 3.13
# The cgi module was removed, but feedparser still tries to import it
import sys
if sys.version_info >= (3, 13):
    import html
    import html.parser
    
    # Create a minimal cgi module replacement
    class CGIModule:
        def escape(self, s, quote=False):
            return html.escape(s, quote=quote)
    
    sys.modules['cgi'] = CGIModule()

# Now we can safely import the rest
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn
from contextlib import asynccontextmanager

from models.database import init_db, get_db
from services.rss_service import RSSService
from models.models import Feed, Article


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    await init_db()
    yield


app = FastAPI(title="StupidRSS", description="A minimalistic RSS reader", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: AsyncSession = Depends(get_db)):
    """Main page showing all feeds and recent articles."""
    rss_service = RSSService(db)
    feeds = await rss_service.get_all_feeds()
    recent_articles = await rss_service.get_recent_articles(limit=20)
    
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "feeds": feeds, "articles": recent_articles}
    )


@app.post("/feeds/add")
async def add_feed(
    request: Request,
    url: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """Add a new RSS feed."""
    rss_service = RSSService(db)
    try:
        feed = await rss_service.add_feed(url)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add feed: {str(e)}")


@app.post("/feeds/{feed_id}/refresh")
async def refresh_feed(feed_id: int, db: AsyncSession = Depends(get_db)):
    """Refresh a specific feed."""
    rss_service = RSSService(db)
    try:
        await rss_service.refresh_feed(feed_id)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to refresh feed: {str(e)}")


@app.delete("/feeds/{feed_id}")
async def delete_feed(feed_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a feed."""
    rss_service = RSSService(db)
    await rss_service.delete_feed(feed_id)
    return {"message": "Feed deleted"}


@app.get("/feeds/{feed_id}/articles", response_class=HTMLResponse)
async def feed_articles(
    request: Request, 
    feed_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """Show articles from a specific feed."""
    rss_service = RSSService(db)
    feed = await rss_service.get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    articles = await rss_service.get_articles_by_feed(feed_id)
    return templates.TemplateResponse(
        "feed_articles.html",
        {"request": request, "feed": feed, "articles": articles}
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
