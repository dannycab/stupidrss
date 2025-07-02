<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# RSS Reader Webapp Instructions

This is a FastAPI-based RSS reader webapp with the following architecture:

## Tech Stack
- **Backend**: FastAPI (async Python web framework)
- **Frontend**: Jinja2 templates with Tailwind CSS
- **Database**: SQLite with SQLAlchemy ORM
- **RSS Parsing**: feedparser library
- **HTTP Client**: httpx for async requests

## Project Structure
- `main.py` - FastAPI application entry point
- `models/` - SQLAlchemy database models
- `routers/` - API route handlers
- `templates/` - Jinja2 HTML templates
- `static/` - CSS, JS, and static assets
- `services/` - Business logic (RSS parsing, feed management)

## Development Guidelines
- Use async/await for all I/O operations
- Follow FastAPI best practices for dependency injection
- Keep the UI minimal and fast with Tailwind CSS
- Implement proper error handling for RSS feeds
- Use SQLAlchemy async sessions for database operations
- Cache RSS feeds appropriately to avoid overloading servers
