from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class Feed(Base):
    __tablename__ = "feeds"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    url = Column(String(500), unique=True, nullable=False, index=True)
    description = Column(Text)
    category = Column(String(100), default="General")  # New: Tech, Sports, News, etc.
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationship to articles
    articles = relationship("Article", back_populates="feed", cascade="all, delete-orphan")


class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    link = Column(String(1000), nullable=False)
    description = Column(Text)
    content = Column(Text)
    full_content = Column(Text)  # New: scraped full article content
    author = Column(String(255))
    published_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    is_saved = Column(Boolean, default=False)  # New: saved for later
    read_at = Column(DateTime, nullable=True)  # New: when it was marked read
    
    # Foreign key to feed
    feed_id = Column(Integer, ForeignKey("feeds.id"), nullable=False, index=True)
    
    # Relationship to feed
    feed = relationship("Feed", back_populates="articles")
