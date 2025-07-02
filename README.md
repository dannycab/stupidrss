# StupidRSS

A fast, minimalistic RSS reader webapp built with FastAPI and Tailwind CSS.

🌐 **Live Demo**: [Documentation](http://localhost:8000) | [RSS Reader App](http://localhost:8000/app)  
🔗 **GitHub**: https://github.com/dannycab/stupidrss

## Features

- 🚀 **Fast**: Built with FastAPI for high performance
- 🎨 **Modern UI**: Clean, responsive design with Tailwind CSS
- 📱 **Mobile-friendly**: Works great on all devices
- 🔄 **Real-time updates**: Async RSS parsing and fetching
- 💾 **SQLite database**: Lightweight, zero-config storage
- 🔗 **Easy feed management**: Add, remove, and refresh feeds with one click

## Tech Stack

- **Backend**: FastAPI (Python async web framework)
- **Frontend**: Jinja2 templates + Tailwind CSS
- **Database**: SQLite with SQLAlchemy ORM
- **RSS Parsing**: feedparser library
- **HTTP Client**: httpx for async requests

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python main.py
   ```

3. **Open your browser** and go to `http://localhost:8000`

4. **Add RSS feeds** and start reading!

## Development

### Running in development mode:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Project Structure:
```
stupidrss/
├── main.py              # FastAPI application entry point
├── models/              # Database models
│   ├── database.py      # Database configuration
│   └── models.py        # SQLAlchemy models
├── services/            # Business logic
│   └── rss_service.py   # RSS parsing and feed management
├── templates/           # Jinja2 HTML templates
│   ├── base.html        # Base template
│   ├── index.html       # Home page
│   └── feed_articles.html # Feed-specific articles
├── static/              # Static assets
│   └── style.css        # Custom CSS
└── requirements.txt     # Python dependencies
```

## Adding Feeds

Simply click "Add Feed" and paste any RSS/Atom feed URL. The app will:
- Validate the feed
- Extract feed metadata
- Fetch initial articles
- Start tracking updates

## API Endpoints

- `GET /` - Home page with all feeds and recent articles
- `POST /feeds/add` - Add a new RSS feed
- `POST /feeds/{feed_id}/refresh` - Refresh a specific feed
- `DELETE /feeds/{feed_id}` - Delete a feed
- `GET /feeds/{feed_id}/articles` - View articles from a specific feed

## Contributing

This is a "vibe coding" project - feel free to fork and customize to your heart's content!

## License

MIT License - do whatever you want with it!
