# KAD Parser

Comprehensive system for parsing court documents from the Russian Arbitration Courts system (КАД Арбитр).

## Features

### Core Functionality
- 🔍 **Case Scraping** - Collect case information from КАД Арбитр
- 📄 **Document Processing** - Parse PDF, DOCX and HTML documents
- 💾 **Data Storage** - PostgreSQL for structured data, MinIO for files
- 🚀 **Async Processing** - Celery with Beat scheduler for background tasks
- 🌐 **REST API** - FastAPI with OpenAPI/Swagger documentation
- 🎯 **Rate Limiting** - Token bucket algorithm for API compliance

### Advanced Features
- 🔐 **Authentication** - JWT tokens and API keys
- 🪝 **Webhooks** - Event notifications with retry logic and HMAC signatures
- 🔌 **Plugin System** - Extensible architecture for custom parsers, processors, exporters
- ⏰ **Scheduled Tasks** - Celery Beat for periodic maintenance and monitoring
- 📊 **Analytics** - Case statistics and reporting
- 📤 **Export** - JSON, CSV, Excel formats
- 🎨 **Web UI** - Modern interface with Tailwind CSS, HTMX, Alpine.js

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL 15+ (with asyncpg)
- **Cache/Queue**: Redis 7+ (Celery broker)
- **Storage**: MinIO (S3-compatible object storage)
- **Tasks**: Celery + Celery Beat
- **Auth**: JWT (python-jose), bcrypt (passlib)
- **Parsing**: BeautifulSoup4, pdfplumber, python-docx
- **HTTP**: httpx (async), curl-cffi
- **Web UI**: Jinja2, Tailwind CSS, HTMX, Alpine.js, Chart.js
- **Export**: openpyxl (Excel), CSV, JSON

## Project Structure

```
kad_parser/
├── src/
│   ├── core/           # Configuration, logging, exceptions
│   ├── scraper/        # КАД Арбитр scraping with rate limiting
│   ├── parser/         # Document parsers (HTML/PDF/DOCX)
│   ├── storage/        # Database models and MinIO storage
│   │   ├── database/   # SQLAlchemy models and repositories
│   │   └── files/      # MinIO file storage
│   ├── tasks/          # Celery tasks and Beat scheduler
│   ├── api/            # FastAPI application
│   │   ├── routes/     # API endpoints (auth, webhooks, plugins, etc.)
│   │   └── schemas/    # Pydantic schemas
│   ├── webhooks/       # Webhook dispatcher and delivery
│   ├── plugins/        # Plugin system (base classes and manager)
│   ├── web/            # Web UI templates and routes
│   └── cli/            # CLI interface
├── plugins/            # User plugins directory
├── tests/              # Tests (unit and integration)
├── docker/             # Docker configuration
└── scripts/            # Utility scripts
```

## Quick Start

### Installation

```bash
# Install dependencies with uv (recommended)
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"

# Install additional dependencies
uv pip install email-validator
```

### Configuration

Copy `.env.example` to `.env` and configure environment variables:

```bash
cp .env.example .env
```

Key variables:
- `SECRET_KEY` - JWT secret key
- `POSTGRES_*` - PostgreSQL connection settings
- `REDIS_*` - Redis connection settings
- `MINIO_*` - MinIO connection settings

### Running with Docker

```bash
# Start all services (API, Worker, Beat, PostgreSQL, Redis, MinIO)
docker-compose -f docker/docker-compose.yml up -d

# Services:
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/api/docs
# - Web UI: http://localhost:8000/ui
# - MinIO Console: http://localhost:9001
```

### Running Locally

```bash
# 1. Start PostgreSQL and Redis
# 2. Run migrations
alembic upgrade head

# 3. Start API server
kad-parser serve
# or
uvicorn src.api.app:app --reload

# 4. Start Celery worker
celery -A src.tasks.celery_app worker --loglevel=info

# 5. Start Celery Beat (for periodic tasks)
celery -A src.tasks.celery_app beat --loglevel=info
```

## Usage

### Authentication

```bash
# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "testuser",
    "password": "securepassword"
  }'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepassword"
  }'

# Create API key
curl -X POST http://localhost:8000/api/auth/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My API Key",
    "expires_days": 30
  }'
```

### Webhooks

```bash
# Create webhook
curl -X POST http://localhost:8000/api/webhooks \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Case Updates",
    "url": "https://your-server.com/webhook",
    "secret": "your_webhook_secret",
    "events": ["case.created", "case.updated"],
    "max_retries": 3,
    "retry_delay": 60
  }'

# List webhooks
curl http://localhost:8000/api/webhooks \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Test webhook
curl -X POST http://localhost:8000/api/webhooks/{webhook_id}/test \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test delivery"}'
```

### Plugins

```bash
# List plugins
curl http://localhost:8000/api/plugins \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Enable/disable plugin
curl -X PATCH http://localhost:8000/api/plugins/{plugin_name}/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Configure plugin
curl -X POST http://localhost:8000/api/plugins/{plugin_name}/configure \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"config": {"option": "value"}}'

# Reload plugins
curl -X POST http://localhost:8000/api/plugins/reload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Cases

```bash
# Scrape case
curl -X POST http://localhost:8000/api/cases/scrape \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"case_number": "А40-123456/2024"}'

# List cases
curl http://localhost:8000/api/cases \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Get case
curl http://localhost:8000/api/cases/{case_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Export cases
curl http://localhost:8000/api/export/cases?format=xlsx \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -O cases.xlsx
```

### CLI

```bash
# Check version
kad-parser version

# Scrape case
kad-parser scrape А40-123456/2024

# Start API server
kad-parser serve --host 0.0.0.0 --port 8000
```

## Development

### Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html --cov-report=term-missing

# Specific module
pytest tests/unit/test_scraper_kad_client.py -v

# Integration tests
pytest tests/integration/ -v
```

### Linting and Formatting

```bash
# Ruff (linting and formatting)
ruff check src/
ruff format src/

# MyPy (type checking)
mypy src/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1

# Show current version
alembic current
```

## Architecture

### Modules

- **core** - Configuration, logging, exception handling
- **scraper** - КАД Арбитр API client with rate limiting and retry logic
- **parser** - Extract data from HTML, PDF, DOCX documents
- **storage** - Repository pattern for database, MinIO for file storage
- **tasks** - Celery tasks for async processing, Beat for scheduling
- **api** - REST API with FastAPI
- **webhooks** - Event notification system with retry logic
- **plugins** - Extensible plugin system
- **web** - Modern web UI
- **cli** - Command-line interface

### Database Models

**Core:**
- `User` - Authentication users
- `APIKey` - API key authentication

**Business:**
- `Case` - Court case
- `Participant` - Case participant
- `Document` - Court document
- `Hearing` - Court hearing
- `ScrapingTask` - Scraping task history

**System:**
- `Webhook` - Webhook configuration
- `WebhookDelivery` - Webhook delivery log

### Webhook Events

**Case Events:**
- `case.created` - New case created
- `case.updated` - Case updated
- `case.scraping.started` - Scraping started
- `case.scraping.completed` - Scraping completed
- `case.scraping.failed` - Scraping failed

**Document Events:**
- `document.created` - Document created
- `document.updated` - Document updated
- `document.parsing.started` - Parsing started
- `document.parsing.completed` - Parsing completed
- `document.parsing.failed` - Parsing failed

**Task Events:**
- `task.started` - Task started
- `task.completed` - Task completed
- `task.failed` - Task failed

### Plugin System

Create custom plugins by extending base classes:

**Parser Plugin:**
```python
from src.plugins.base import ParserPlugin

class MyParserPlugin(ParserPlugin):
    @property
    def name(self) -> str:
        return "my_parser"

    async def parse(self, content: bytes, content_type: str) -> dict:
        # Parse document
        return {"text": "parsed content"}

    def supports_content_type(self, content_type: str) -> bool:
        return content_type == "application/my-format"
```

See `plugins/README.md` for complete documentation.

### Scheduled Tasks (Celery Beat)

- **Retry failed webhooks** - Every minute
- **Clean up old deliveries** - Daily at 2 AM
- **Update case statistics** - Hourly
- **Check stuck tasks** - Every 15 minutes
- **Cleanup expired sessions** - Daily at 3 AM

## API Documentation

Interactive API documentation available at:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## Performance

- Async/await throughout for maximum concurrency
- Connection pooling for database and HTTP
- Rate limiting with token bucket algorithm
- Celery for distributed task processing
- Redis for caching and message broker
- MinIO for efficient file storage

## Security

- JWT token-based authentication
- API key authentication
- Password hashing with bcrypt
- HMAC signature verification for webhooks
- CORS middleware
- Input validation with Pydantic
- SQL injection prevention with SQLAlchemy
- XSS protection

## Future Enhancements

- Prometheus + Grafana monitoring
- Elasticsearch for full-text search
- ML-based case categorization
- Admin panel for system management
- WebSocket support for real-time updates
- GraphQL API
- Multi-tenant support

## License

MIT License - see [LICENSE](LICENSE)

## Author

Andrew821667

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
