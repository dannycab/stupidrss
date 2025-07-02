# StupidRSS

> **Vibe Coding Project Notice**
>
> This project is developed in a freeform, improvisational, and experimental style. **No pull requests will be honored.**
>
> If you have a feature request or bug, please [open an issue](https://github.com/dannycab/stupidrss/issues) and I'll vibe code it (maybe it works, maybe not). Thanks for understanding!

A fast, minimalistic RSS reader webapp built with FastAPI and Tailwind CSS.

🌐 **Live Demo**: [Documentation](http://dannycaballero.info/stupidrss)  
🔗 **GitHub**: https://github.com/dannycab/stupidrss

## Features

- 🚀 **Fast**: Built with FastAPI for high performance
- 🎨 **Modern UI**: Clean, responsive design with Tailwind CSS
- 📱 **Mobile-friendly**: Works great on all devices
- 🔄 **Real-time updates**: Async RSS parsing and fetching
- 💾 **SQLite database**: Lightweight, zero-config storage
- 🔗 **Easy feed management**: Add, remove, and refresh feeds with one click
- 🧹 **Smart Content Cleaning**: Automatically strips HTML tags while preserving formatting
- 📺 **YouTube-Optimized**: Removes spam and duplicate content from video feeds
- 🎯 **Enhanced UX**: Streamlined buttons, improved navigation, and consistent UI
- 🔍 **Filter Support**: Built-in article filtering and search capabilities

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

## Screenshots

### Main Page - Feed Overview
![Main Page](docs/images/main-page.png)

### Article Reading Experience  
![Article Page](docs/images/article-page.png)

### Admin Panel - Feed Management
![Admin Page](docs/images/admin-page.png)

### Saved Articles
![Saved Page](docs/images/saved-page.png)

## API Routes

- `GET /app` - Main RSS reader application
- `GET /docs` - Interactive OpenAPI documentation
- `GET /redoc` - Alternative API documentation

### 🔗 **REST API Endpoints:**
- `GET /api/feeds` - List all feeds
- `GET /api/feeds/{id}` - Get specific feed
- `GET /api/articles` - Recent articles  
- `GET /api/feeds/{id}/articles` - Feed-specific articles
- `PUT /api/feeds/{id}` - Update feed metadata
- `POST /feeds/add` - Add new feed
- `DELETE /feeds/{id}` - Delete feed
- `POST /feeds/{id}/refresh` - Refresh feed

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
- Automatically clean HTML content for better readability
- Remove duplicate descriptions and spam content

## Content Features

**Smart Content Cleaning**: StupidRSS automatically processes all article content to:
- Strip HTML tags while preserving formatting (lists, paragraphs, line breaks)
- Remove YouTube spam and promotional content
- Eliminate duplicate descriptions
- Convert HTML entities to readable text
- Maintain proper list formatting with bullets and numbering

**Enhanced User Experience**:
- Standardized "Add Feed" and "Delete" buttons across all pages
- Enhanced delete confirmation requiring "DELETE" to be typed
- Streamlined feed display on the home page
- Working filter buttons for article management
- Consistent UI styling and responsive design

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
