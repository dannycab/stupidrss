from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.models import Feed, Article
import feedparser
import httpx
from datetime import datetime
from dateutil import parser as date_parser
from typing import List, Optional


class RSSService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_feed(self, url: str) -> Feed:
        """Add a new RSS feed."""
        # Validate the feed by parsing it first
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            
        parsed_feed = feedparser.parse(response.text)
        if parsed_feed.bozo:
            raise ValueError("Invalid RSS feed")
        
        # Create feed object
        feed = Feed(
            title=parsed_feed.feed.get('title', 'Unknown Feed'),
            url=url,
            description=parsed_feed.feed.get('description', ''),
            last_updated=datetime.utcnow()
        )
        
        self.db.add(feed)
        await self.db.commit()
        await self.db.refresh(feed)
        
        # Fetch initial articles
        await self._fetch_articles(feed, parsed_feed)
        
        return feed

    async def get_all_feeds(self) -> List[Feed]:
        """Get all active feeds."""
        result = await self.db.execute(
            select(Feed).where(Feed.is_active == True).order_by(Feed.title)
        )
        return result.scalars().all()

    async def get_feed_by_id(self, feed_id: int) -> Optional[Feed]:
        """Get a feed by ID."""
        result = await self.db.execute(select(Feed).where(Feed.id == feed_id))
        return result.scalar_one_or_none()

    async def refresh_feed(self, feed_id: int):
        """Refresh articles for a specific feed."""
        feed = await self.get_feed_by_id(feed_id)
        if not feed:
            raise ValueError("Feed not found")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(feed.url, timeout=10.0)
            response.raise_for_status()
            
        parsed_feed = feedparser.parse(response.text)
        await self._fetch_articles(feed, parsed_feed)
        
        # Update feed last_updated timestamp
        feed.last_updated = datetime.utcnow()
        await self.db.commit()

    async def delete_feed(self, feed_id: int):
        """Delete a feed and all its articles."""
        feed = await self.get_feed_by_id(feed_id)
        if feed:
            await self.db.delete(feed)
            await self.db.commit()

    async def get_recent_articles(self, limit: int = 20) -> List[Article]:
        """Get recent articles across all feeds."""
        result = await self.db.execute(
            select(Article)
            .join(Feed)
            .where(Feed.is_active == True)
            .order_by(desc(Article.published_date))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_articles_by_feed(self, feed_id: int) -> List[Article]:
        """Get all articles for a specific feed."""
        result = await self.db.execute(
            select(Article)
            .where(Article.feed_id == feed_id)
            .order_by(desc(Article.published_date))
        )
        return result.scalars().all()

    async def _fetch_articles(self, feed: Feed, parsed_feed):
        """Fetch and store articles from a parsed feed."""
        for entry in parsed_feed.entries:
            # Check if article already exists
            existing = await self.db.execute(
                select(Article).where(Article.link == entry.link)
            )
            if existing.scalar_one_or_none():
                continue  # Skip existing articles
            
            # Parse published date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'published'):
                try:
                    published_date = date_parser.parse(entry.published)
                except:
                    pass
            
            # Create article
            article = Article(
                title=entry.get('title', 'No Title'),
                link=entry.get('link', ''),
                description=entry.get('summary', ''),
                content=entry.get('content', [{}])[0].get('value', '') if entry.get('content') else '',
                author=entry.get('author', ''),
                published_date=published_date or datetime.utcnow(),
                feed_id=feed.id
            )
            
            self.db.add(article)
        
        await self.db.commit()
