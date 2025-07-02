from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update, func
from sqlalchemy.orm import selectinload
from models.models import Feed, Article
import feedparser
import httpx
from datetime import datetime
from dateutil import parser as date_parser
from typing import List, Optional
from bs4 import BeautifulSoup
from readability import Document
import re


class RSSService:
    def __init__(self, db: AsyncSession):
        self.db = db
        # Standard headers to avoid 403 errors from RSS feeds
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; StupidRSS/1.0; RSS Reader)',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }

    async def add_feed(self, url: str, category: str = "General") -> Feed:
        """Add a new RSS feed with optional category."""
        # Validate the feed by parsing it first
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, timeout=10.0)
            response.raise_for_status()
            
        parsed_feed = feedparser.parse(response.text)
        if parsed_feed.bozo:
            raise ValueError("Invalid RSS feed")
        
        # Create feed object
        feed = Feed(
            title=parsed_feed.feed.get('title', 'Unknown Feed'),
            url=url,
            description=parsed_feed.feed.get('description', ''),
            category=category,
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
            select(Feed)
            .options(selectinload(Feed.articles))
            .where(Feed.is_active == True)
            .order_by(Feed.category, Feed.title)
        )
        return result.scalars().all()

    async def get_feeds_by_category(self) -> dict:
        """Get feeds grouped by category."""
        feeds = await self.get_all_feeds()
        categories = {}
        for feed in feeds:
            if feed.category not in categories:
                categories[feed.category] = []
            categories[feed.category].append(feed)
        return categories

    async def get_feed_by_id(self, feed_id: int) -> Optional[Feed]:
        """Get a feed by ID."""
        result = await self.db.execute(select(Feed).where(Feed.id == feed_id))
        return result.scalar_one_or_none()

    async def update_feed_category(self, feed_id: int, category: str):
        """Update a feed's category."""
        await self.db.execute(
            update(Feed).where(Feed.id == feed_id).values(category=category)
        )
        await self.db.commit()

    async def refresh_feed(self, feed_id: int):
        """Refresh articles for a specific feed."""
        feed = await self.get_feed_by_id(feed_id)
        if not feed:
            raise ValueError("Feed not found")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(feed.url, headers=self.headers, timeout=10.0)
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

    async def get_recent_articles(self, limit: int = 20, offset: int = 0, unread_only: bool = False) -> List[Article]:
        """Get recent articles across all feeds with pagination."""
        query = (
            select(Article)
            .options(selectinload(Article.feed))
            .join(Feed)
            .where(Feed.is_active == True)
        )
        
        if unread_only:
            query = query.where(Article.is_read == False)
            
        query = query.order_by(desc(Article.published_date)).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_articles_by_category(self, category: str, limit: int = 20, offset: int = 0) -> List[Article]:
        """Get articles from feeds in a specific category with pagination."""
        query = (
            select(Article)
            .options(selectinload(Article.feed))
            .join(Feed)
            .where(Feed.is_active == True)
            .where(Feed.category == category)
            .order_by(desc(Article.published_date))
            .offset(offset)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_total_articles_count(self, category: str = None) -> int:
        """Get total count of articles, optionally filtered by category."""
        query = (
            select(func.count(Article.id))
            .join(Feed)
            .where(Feed.is_active == True)
        )
        
        if category:
            query = query.where(Feed.category == category)
        
        result = await self.db.execute(query)
        return result.scalar()

    async def get_saved_articles(self) -> List[Article]:
        """Get all saved articles."""
        result = await self.db.execute(
            select(Article)
            .options(selectinload(Article.feed))
            .join(Feed)
            .where(Feed.is_active == True, Article.is_saved == True)
            .order_by(desc(Article.published_date))
        )
        return result.scalars().all()

    async def get_articles_by_feed(self, feed_id: int) -> List[Article]:
        """Get all articles for a specific feed."""
        result = await self.db.execute(
            select(Article)
            .options(selectinload(Article.feed))
            .where(Article.feed_id == feed_id)
            .order_by(desc(Article.published_date))
        )
        return result.scalars().all()

    async def get_article_by_id(self, article_id: int) -> Optional[Article]:
        """Get an article by ID with feed relationship loaded."""
        result = await self.db.execute(
            select(Article)
            .options(selectinload(Article.feed))
            .where(Article.id == article_id)
        )
        return result.scalar_one_or_none()

    async def mark_article_read(self, article_id: int, is_read: bool = True):
        """Mark an article as read or unread."""
        read_at = datetime.utcnow() if is_read else None
        await self.db.execute(
            update(Article)
            .where(Article.id == article_id)
            .values(is_read=is_read, read_at=read_at)
        )
        await self.db.commit()

    async def save_article(self, article_id: int, is_saved: bool = True):
        """Save or unsave an article."""
        await self.db.execute(
            update(Article)
            .where(Article.id == article_id)
            .values(is_saved=is_saved)
        )
        await self.db.commit()

    async def scrape_article_content(self, article_id: int):
        """Scrape full article content for better reading experience."""
        article = await self.get_article_by_id(article_id)
        if not article or article.full_content:
            return  # Already scraped or article not found
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(article.link, headers=self.headers, timeout=15.0)
                response.raise_for_status()
                
            # Use readability to extract main content
            doc = Document(response.text)
            
            # Clean up the content
            soup = BeautifulSoup(doc.content(), 'html.parser')
            
            # Remove unwanted elements
            for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                elem.decompose()
            
            # Get clean text content
            full_content = str(soup)
            
            # Update article with full content
            await self.db.execute(
                update(Article)
                .where(Article.id == article_id)
                .values(full_content=full_content)
            )
            await self.db.commit()
            
        except Exception as e:
            print(f"Failed to scrape article {article_id}: {e}")

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

    async def export_opml(self) -> str:
        """Export all feeds to OPML format."""
        feeds = await self.get_all_feeds()
        feeds_by_category = await self.get_feeds_by_category()
        
        opml_header = '''<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
    <head>
        <title>StupidRSS Feeds</title>
        <dateCreated>{date}</dateCreated>
        <ownerName>StupidRSS</ownerName>
    </head>
    <body>'''.format(date=datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'))
        
        opml_body = ""
        for category, category_feeds in feeds_by_category.items():
            opml_body += f'\n        <outline text="{category}" title="{category}">\n'
            for feed in category_feeds:
                # Escape XML special characters
                title = feed.title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                description = (feed.description or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                opml_body += f'            <outline type="rss" text="{title}" title="{title}" xmlUrl="{feed.url}" description="{description}"/>\n'
            opml_body += '        </outline>\n'
        
        opml_footer = '''    </body>
</opml>'''
        
        return opml_header + opml_body + opml_footer

    async def import_opml(self, opml_content: str) -> dict:
        """Import feeds from OPML content with detailed logging and validation."""
        from xml.etree import ElementTree as ET
        import logging
        
        # Set up logging
        logger = logging.getLogger(__name__)
        
        try:
            root = ET.fromstring(opml_content)
            logger.info("Successfully parsed OPML file")
        except ET.ParseError as e:
            logger.error(f"Failed to parse OPML: {str(e)}")
            raise ValueError(f"Invalid OPML format: {str(e)}")
        
        imported_feeds = []
        errors = []
        validation_details = []
        
        # Build a parent map for finding categories
        parent_map = {c: p for p in root.iter() for c in p}
        
        # Find all outline elements that have xmlUrl (RSS feeds)
        feed_outlines = root.findall('.//outline[@xmlUrl]')
        logger.info(f"Found {len(feed_outlines)} feeds in OPML file")
        
        for i, outline in enumerate(feed_outlines, 1):
            url = outline.get('xmlUrl')
            title = outline.get('text') or outline.get('title') or f'Unknown Feed {i}'
            description = outline.get('description', '')
            
            logger.info(f"Processing feed {i}/{len(feed_outlines)}: {title} ({url})")
            
            try:
                # Validate URL format
                if not url or not url.strip():
                    error_msg = f"Feed '{title}' has empty or missing URL"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
                
                # Clean and validate URL
                url = url.strip()
                if not (url.startswith('http://') or url.startswith('https://')):
                    error_msg = f"Feed '{title}' has invalid URL format: {url}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
                
                # Try to determine category from parent outline
                category = "General"
                parent = parent_map.get(outline)
                if parent is not None and parent.tag == 'outline' and not parent.get('xmlUrl'):
                    category = parent.get('text') or parent.get('title') or "General"
                
                logger.debug(f"Feed '{title}' assigned to category: {category}")
                
                # Check if feed already exists
                existing_feed_result = await self.db.execute(
                    select(Feed).where(Feed.url == url)
                )
                existing_feed = existing_feed_result.scalar_one_or_none()
                
                if existing_feed:
                    error_msg = f"Feed already exists: {title} ({url})"
                    logger.info(error_msg)
                    errors.append(error_msg)
                    continue
                
                # Validate RSS feed before adding
                logger.debug(f"Validating RSS feed: {url}")
                validation_result = await self._validate_rss_feed(url, title)
                validation_details.append(validation_result)
                
                if not validation_result['is_valid']:
                    error_msg = f"Feed '{title}' failed validation: {validation_result['error']}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue
                
                # Add the feed
                logger.info(f"Adding feed: {title}")
                feed = await self.add_feed(url, category)
                imported_feeds.append({
                    'title': feed.title,
                    'url': feed.url,
                    'category': feed.category
                })
                logger.info(f"Successfully imported feed: {feed.title}")
                
            except Exception as e:
                error_msg = f"Failed to import feed '{title}' ({url}): {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        logger.info(f"OPML import completed: {len(imported_feeds)} successful, {len(errors)} errors")
        
        return {
            'imported_count': len(imported_feeds),
            'imported_feeds': imported_feeds,
            'errors': errors,
            'validation_details': validation_details,
            'total_processed': len(feed_outlines)
        }

    async def _validate_rss_feed(self, url: str, title: str) -> dict:
        """Validate an RSS feed URL and return detailed information."""
        import logging
        
        logger = logging.getLogger(__name__)
        
        validation_result = {
            'url': url,
            'title': title,
            'is_valid': False,
            'error': None,
            'feed_title': None,
            'feed_type': None,
            'item_count': 0,
            'response_code': None,
            'redirect_url': None
        }
        
        try:
            logger.debug(f"Making HTTP request to: {url}")
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers, timeout=15.0)
                validation_result['response_code'] = response.status_code
                
                # Check for redirects
                if len(response.history) > 0:
                    original_url = response.history[0].url
                    final_url = response.url
                    validation_result['redirect_url'] = str(final_url)
                    logger.info(f"Feed redirected: {original_url} -> {final_url}")
                
                response.raise_for_status()
            
            logger.debug(f"Parsing RSS content for: {url}")
            parsed_feed = feedparser.parse(response.text)
            
            # Check if feedparser detected any issues
            if parsed_feed.bozo:
                validation_result['error'] = f"Feed parser error: {parsed_feed.bozo_exception}"
                logger.warning(f"Feed has parsing issues: {url} - {validation_result['error']}")
                return validation_result
            
            # Extract feed information
            feed_info = parsed_feed.feed
            validation_result['feed_title'] = feed_info.get('title', 'Unknown')
            validation_result['item_count'] = len(parsed_feed.entries)
            
            # Determine feed type
            if hasattr(parsed_feed, 'version'):
                validation_result['feed_type'] = parsed_feed.version
            
            # Check if feed has entries
            if validation_result['item_count'] == 0:
                validation_result['error'] = "Feed contains no entries"
                logger.warning(f"Feed has no entries: {url}")
                return validation_result
            
            # Check if feed has required fields
            if not validation_result['feed_title'] or validation_result['feed_title'] == 'Unknown':
                logger.warning(f"Feed has no title: {url}")
            
            validation_result['is_valid'] = True
            logger.debug(f"Feed validation successful: {url} ({validation_result['item_count']} items)")
            
        except httpx.HTTPStatusError as e:
            validation_result['error'] = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
            logger.error(f"HTTP error for feed {url}: {validation_result['error']}")
        except httpx.RequestError as e:
            validation_result['error'] = f"Network error: {str(e)}"
            logger.error(f"Network error for feed {url}: {validation_result['error']}")
        except Exception as e:
            validation_result['error'] = f"Validation error: {str(e)}"
            logger.error(f"Unexpected error validating feed {url}: {validation_result['error']}")
        
        return validation_result

    def extract_youtube_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from various YouTube URL formats."""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:m\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in youtube_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def embed_youtube_videos(self, content: str) -> str:
        """Find YouTube links in content and add embedded videos."""
        if not content:
            return content
        
        # Find all URLs in the content
        url_pattern = r'https?://[^\s<>"\']+(?:youtube\.com|youtu\.be)[^\s<>"\']*'
        urls = re.findall(url_pattern, content, re.IGNORECASE)
        
        modified_content = content
        embedded_videos = set()  # Track to avoid duplicates
        
        for url in urls:
            video_id = self.extract_youtube_video_id(url)
            if video_id and video_id not in embedded_videos:
                # Create YouTube embed HTML
                embed_html = f'''
                <div class="youtube-embed-container my-6">
                    <div class="relative w-full h-0 pb-[56.25%]"> <!-- 16:9 aspect ratio -->
                        <iframe 
                            class="absolute top-0 left-0 w-full h-full rounded-lg shadow-lg"
                            src="https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1"
                            title="YouTube video player"
                            frameborder="0"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                            allowfullscreen>
                        </iframe>
                    </div>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-2 text-center">
                        <a href="{url}" target="_blank" rel="noopener noreferrer" class="hover:text-blue-500">
                            Watch on YouTube
                        </a>
                    </p>
                </div>
                '''
                
                # Add the embed after the link, or replace the link if it's on its own line
                if f'<a href="{url}"' in modified_content:
                    # If it's already a link, add embed after it
                    link_pattern = f'<a[^>]*href="{re.escape(url)}"[^>]*>.*?</a>'
                    modified_content = re.sub(link_pattern, lambda m: m.group(0) + embed_html, modified_content)
                else:
                    # If it's just a plain URL, replace it with a link + embed
                    link_html = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
                    modified_content = modified_content.replace(url, link_html + embed_html)
                
                embedded_videos.add(video_id)
        
        return modified_content
