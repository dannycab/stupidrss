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
from fastapi import FastAPI, Request, Depends, HTTPException, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from sqlalchemy import func, select, update
import uvicorn
from contextlib import asynccontextmanager
from pydantic import BaseModel
from datetime import datetime

from models.database import init_db, get_db
from services.rss_service import RSSService
from models.models import Feed, Article

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

# Set specific log levels
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    await init_db()
    yield


app = FastAPI(title="StupidRSS", description="A minimalistic RSS reader", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/docs-static", StaticFiles(directory="docs"), name="docs-static")

# Templates
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def read_docs(request: Request):
    """Documentation homepage."""
    with open("docs/index.html", "r") as f:
        content = f.read()
    return HTMLResponse(content=content)


@app.get("/app", response_class=HTMLResponse)
async def read_app(
    request: Request, 
    category: str = None,
    page: int = 1,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Main RSS reader application."""
    rss_service = RSSService(db)
    feeds = await rss_service.get_all_feeds()
    feeds_by_category = await rss_service.get_feeds_by_category()
    
    # Calculate offset
    offset = (page - 1) * limit
    
    # Get articles with pagination and optional category filter
    if category and category != "all":
        recent_articles = await rss_service.get_articles_by_category(category, limit=limit, offset=offset)
    else:
        recent_articles = await rss_service.get_recent_articles(limit=limit, offset=offset)
    
    # Get total count for pagination
    total_articles = await rss_service.get_total_articles_count(category if category != "all" else None)
    
    # Check if there are more articles
    has_more = (offset + limit) < total_articles
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "feeds": feeds, 
            "feeds_by_category": feeds_by_category, 
            "articles": recent_articles,
            "current_category": category or "all",
            "current_page": page,
            "has_more": has_more,
            "total_articles": total_articles
        }
    )


@app.post("/feeds/add")
async def add_feed(
    request: Request,
    url: str = Form(...),
    category: str = Form("General"),
    db: AsyncSession = Depends(get_db)
):
    """Add a new RSS feed."""
    rss_service = RSSService(db)
    try:
        feed = await rss_service.add_feed(url, category.strip() or "General")
        # Check if request came from admin panel
        referer = request.headers.get("referer", "")
        if "/admin" in referer:
            return RedirectResponse(url="/app/admin", status_code=303)
        return RedirectResponse(url="/app", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add feed: {str(e)}")


@app.post("/feeds/{feed_id}/refresh")
async def refresh_feed(feed_id: int, db: AsyncSession = Depends(get_db)):
    """Refresh a specific feed."""
    rss_service = RSSService(db)
    try:
        await rss_service.refresh_feed(feed_id)
        return RedirectResponse(url="/app", status_code=303)
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


@app.get("/articles/{article_id}", response_class=HTMLResponse)
async def read_article(
    request: Request, 
    article_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """Show full article for reading within the app."""
    rss_service = RSSService(db)
    article = await rss_service.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Mark as read when viewing
    if not article.is_read:
        await rss_service.mark_article_read(article_id, True)
        await db.refresh(article)
    
    return templates.TemplateResponse(
        "article.html",
        {"request": request, "article": article}
    )


@app.get("/saved", response_class=HTMLResponse)
async def saved_articles(request: Request, db: AsyncSession = Depends(get_db)):
    """Show saved articles."""
    rss_service = RSSService(db)
    articles = await rss_service.get_saved_articles()
    
    return templates.TemplateResponse(
        "saved.html",
        {"request": request, "articles": articles}
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, db: AsyncSession = Depends(get_db)):
    """Admin panel for managing feeds and articles."""
    rss_service = RSSService(db)
    
    # Get stats
    feeds = await rss_service.get_all_feeds()
    feeds_by_category = await rss_service.get_feeds_by_category()
    
    # Count articles
    total_articles_result = await db.execute(select(func.count(Article.id)))
    total_articles = total_articles_result.scalar()
    
    saved_articles_result = await db.execute(
        select(func.count(Article.id)).where(Article.is_saved == True)
    )
    saved_articles = saved_articles_result.scalar()
    
    categories = list(feeds_by_category.keys())
    
    stats = {
        'total_feeds': len(feeds),
        'total_articles': total_articles,
        'saved_articles': saved_articles,
        'categories': categories
    }
    
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request, 
            "stats": stats, 
            "feeds_by_category": feeds_by_category
        }
    )


# Request models for API
class ReadStatusRequest(BaseModel):
    is_read: bool

class SaveStatusRequest(BaseModel):
    is_saved: bool

class UpdateFeedRequest(BaseModel):
    title: str = None
    category: str = None


# API Endpoints for programmatic access
@app.get("/api/feeds")
async def api_get_feeds(db: AsyncSession = Depends(get_db)):
    """Get all feeds as JSON."""
    rss_service = RSSService(db)
    feeds = await rss_service.get_all_feeds()
    return [{"id": f.id, "title": f.title, "url": f.url, "description": f.description, 
             "last_updated": f.last_updated, "created_at": f.created_at} for f in feeds]


@app.get("/api/feeds/{feed_id}")
async def api_get_feed(feed_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific feed as JSON."""
    rss_service = RSSService(db)
    feed = await rss_service.get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"id": feed.id, "title": feed.title, "url": feed.url, "description": feed.description,
            "last_updated": feed.last_updated, "created_at": feed.created_at}


@app.get("/api/articles")
async def api_get_articles(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get recent articles as JSON."""
    rss_service = RSSService(db)
    articles = await rss_service.get_recent_articles(limit=limit)
    return [{"id": a.id, "title": a.title, "link": a.link, "description": a.description,
             "author": a.author, "published_date": a.published_date, "feed_id": a.feed_id,
             "feed_title": a.feed.title} for a in articles]


@app.get("/api/feeds/{feed_id}/articles")
async def api_get_feed_articles(feed_id: int, db: AsyncSession = Depends(get_db)):
    """Get articles from a specific feed as JSON."""
    rss_service = RSSService(db)
    feed = await rss_service.get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    articles = await rss_service.get_articles_by_feed(feed_id)
    return [{"id": a.id, "title": a.title, "link": a.link, "description": a.description,
             "author": a.author, "published_date": a.published_date} for a in articles]


@app.put("/api/feeds/{feed_id}")
async def api_update_feed(
    feed_id: int, 
    request: UpdateFeedRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update a feed's metadata including title and category."""
    rss_service = RSSService(db)
    feed = await rss_service.get_feed_by_id(feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    if request.title:
        feed.title = request.title
    if request.category:
        feed.category = request.category
    
    await db.commit()
    return {"message": "Feed updated", "id": feed.id, "title": feed.title, "category": feed.category}


@app.post("/api/articles/{article_id}/read")
async def api_mark_article_read(
    article_id: int, 
    request: ReadStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """Mark an article as read or unread."""
    rss_service = RSSService(db)
    article = await rss_service.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    await rss_service.mark_article_read(article_id, request.is_read)
    return {"message": "Read status updated", "is_read": request.is_read}


@app.post("/api/articles/{article_id}/save")
async def api_save_article(
    article_id: int, 
    request: SaveStatusRequest,
    db: AsyncSession = Depends(get_db)
):
    """Save or unsave an article."""
    rss_service = RSSService(db)
    article = await rss_service.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    await rss_service.save_article(article_id, request.is_saved)
    return {"message": "Save status updated", "is_saved": request.is_saved}


@app.post("/api/articles/{article_id}/scrape")
async def api_scrape_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Scrape full content for an article."""
    rss_service = RSSService(db)
    article = await rss_service.get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    await rss_service.scrape_article_content(article_id)
    return {"message": "Content scraped successfully"}


# Admin API endpoints
@app.post("/api/feeds/refresh-all")
async def api_refresh_all_feeds(db: AsyncSession = Depends(get_db)):
    """Refresh all active feeds."""
    rss_service = RSSService(db)
    feeds = await rss_service.get_all_feeds()
    
    for feed in feeds:
        try:
            await rss_service.refresh_feed(feed.id)
        except Exception as e:
            print(f"Failed to refresh feed {feed.id}: {e}")
    
    return {"message": f"Refreshed {len(feeds)} feeds"}

@app.post("/api/articles/mark-all-read")
async def api_mark_all_read(db: AsyncSession = Depends(get_db)):
    """Mark all articles as read."""
    await db.execute(
        update(Article).values(is_read=True, read_at=datetime.utcnow())
    )
    await db.commit()
    
    return {"message": "All articles marked as read"}


@app.get("/api/opml/export")
async def api_export_opml(db: AsyncSession = Depends(get_db)):
    """Export all feeds as OPML."""
    from fastapi.responses import Response
    
    rss_service = RSSService(db)
    opml_content = await rss_service.export_opml()
    
    return Response(
        content=opml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": "attachment; filename=stupidrss_feeds.opml"
        }
    )


@app.post("/api/opml/import")
async def api_import_opml(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Import feeds from OPML file with detailed validation and logging."""
    logger = logging.getLogger(__name__)
    
    # Validate file type
    if not file.filename.lower().endswith(('.opml', '.xml')):
        logger.warning(f"Invalid file type uploaded: {file.filename}")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Expected .opml or .xml file, got: {file.filename}"
        )
    
    logger.info(f"Processing OPML import from file: {file.filename}")
    
    try:
        # Read file content
        content = await file.read()
        
        # Validate file size (max 10MB)
        if len(content) > 10 * 1024 * 1024:
            logger.warning(f"OPML file too large: {len(content)} bytes")
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
        
        # Decode content
        try:
            opml_content = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                opml_content = content.decode('latin-1')
                logger.info("Decoded OPML using latin-1 encoding")
            except UnicodeDecodeError:
                logger.error("Failed to decode OPML file with UTF-8 or latin-1")
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid file encoding. Please ensure the file is encoded in UTF-8."
                )
        
        logger.debug(f"OPML content length: {len(opml_content)} characters")
        
        rss_service = RSSService(db)
        result = await rss_service.import_opml(opml_content)
        
        # Log summary
        logger.info(
            f"OPML import completed: {result['imported_count']}/{result['total_processed']} feeds imported, "
            f"{len(result['errors'])} errors"
        )
        
        # Log validation details if available
        if 'validation_details' in result:
            valid_feeds = [v for v in result['validation_details'] if v['is_valid']]
            invalid_feeds = [v for v in result['validation_details'] if not v['is_valid']]
            
            logger.info(f"Feed validation: {len(valid_feeds)} valid, {len(invalid_feeds)} invalid")
            
            # Log details about invalid feeds
            for invalid_feed in invalid_feeds:
                logger.warning(
                    f"Invalid feed: {invalid_feed['title']} ({invalid_feed['url']}) - "
                    f"Error: {invalid_feed['error']}"
                )
        
        return result
        
    except ValueError as e:
        logger.error(f"OPML parsing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid OPML format: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during OPML import: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to import OPML: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
