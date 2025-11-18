# Architecture Documentation

## System Overview

KAD Parser is a comprehensive system for scraping and processing court documents from the Russian Arbitration Courts system (КАД Арбитр). It follows a modern async-first architecture with clear separation of concerns.

## Architecture Principles

1. **Async-First**: Async/await throughout for maximum concurrency
2. **Repository Pattern**: Database access abstraction
3. **Dependency Injection**: FastAPI dependencies for clean code
4. **Plugin Architecture**: Extensible via plugins
5. **Event-Driven**: Webhook system for notifications
6. **Scheduled Tasks**: Celery Beat for periodic operations

## Layers

### 1. API Layer (`src/api/`)

**FastAPI Application** with:
- OpenAPI/Swagger documentation
- JWT and API key authentication
- CORS middleware
- Request validation with Pydantic
- Async route handlers

**Routes:**
- `/auth` - Authentication (register, login, API keys)
- `/webhooks` - Webhook management
- `/plugins` - Plugin management
- `/cases` - Case CRUD operations
- `/documents` - Document management
- `/analytics` - Statistics and reporting
- `/export` - Data export (JSON, CSV, Excel)

### 2. Business Logic Layer

**Scraper** (`src/scraper/`):
- `KadArbitrClient` - HTTP client for КАД Арбитр API
- `RateLimiter` - Token bucket rate limiting
- Retry logic with exponential backoff
- Session management

**Parser** (`src/parser/`):
- `HTMLCaseParser` - Extract data from case cards
- `PDFDocumentParser` - Extract text from PDFs
- `DOCXDocumentParser` - Extract text from DOCX

**Webhooks** (`src/webhooks/`):
- `WebhookDispatcher` - Event dispatching
- HMAC signature generation
- Retry logic with exponential backoff
- Delivery tracking

**Plugins** (`src/plugins/`):
- `PluginManager` - Plugin loading and lifecycle
- Base classes for different plugin types
- Hook system for lifecycle events

### 3. Data Layer

**Storage** (`src/storage/`):

**Database** (`src/storage/database/`):
- SQLAlchemy 2.0 async models
- Alembic migrations
- Repository pattern for data access
- Connection pooling

**Models:**
```
┌─────────────┐
│    User     │
│  APIKey     │
└─────────────┘
       │
       ├─────────────┐
       │             │
┌──────▼──────┐ ┌───▼────────┐
│   Webhook   │ │    Case    │
│WebhookDelivery│  Participant│
└─────────────┘ │  Document  │
                │  Hearing   │
                └────────────┘
                       │
                ┌──────▼────────┐
                │ScrapingTask   │
                └───────────────┘
```

**File Storage** (`src/storage/files/`):
- MinIO (S3-compatible) for documents
- Presigned URLs for secure access
- Automatic bucket creation

### 4. Task Layer (`src/tasks/`)

**Celery Workers:**
- `scrape_case_task` - Scrape case from КАД Арбитр
- `parse_document_task` - Parse document content
- `retry_failed_webhooks_task` - Retry failed webhook deliveries

**Celery Beat Scheduler:**
- Retry failed webhooks (every minute)
- Cleanup old deliveries (daily)
- Update statistics (hourly)
- Check stuck tasks (every 15 minutes)
- Cleanup expired sessions (daily)

### 5. Presentation Layer

**Web UI** (`src/web/`):
- Server-side rendering with Jinja2
- Tailwind CSS for styling
- HTMX for dynamic updates
- Alpine.js for interactivity
- Chart.js for visualizations

**CLI** (`src/cli/`):
- Typer-based command-line interface
- Rich formatting
- Interactive prompts

## Data Flow

### Scraping Flow

```
User Request
    │
    ▼
API Endpoint (/cases/scrape)
    │
    ▼
Celery Task (scrape_case_task)
    │
    ├─► KadArbitrClient
    │   └─► КАД Арбитр API
    │
    ├─► HTMLCaseParser
    │   └─► Extract case data
    │
    ├─► Repository Layer
    │   └─► Save to PostgreSQL
    │
    ├─► MinIO Storage
    │   └─► Store document files
    │
    ├─► WebhookDispatcher
    │   └─► Send event notifications
    │
    └─► Response
```

### Webhook Delivery Flow

```
Event Trigger
    │
    ▼
WebhookDispatcher.dispatch()
    │
    ├─► Find subscribed webhooks
    │
    ├─► Create WebhookDelivery records
    │
    ├─► Attempt delivery
    │   ├─► Generate HMAC signature
    │   ├─► HTTP POST to webhook URL
    │   ├─► Record response
    │   └─► Update statistics
    │
    └─► On failure:
        ├─► Schedule retry (exponential backoff)
        └─► Celery Beat picks up for retry
```

### Plugin Lifecycle

```
Application Startup
    │
    ▼
PluginManager.load_plugins()
    │
    ├─► Scan plugins directory
    │
    ├─► For each plugin file:
    │   ├─► Import module
    │   ├─► Find Plugin classes
    │   ├─► Instantiate plugin
    │   ├─► Call plugin.initialize()
    │   └─► Register hooks
    │
    └─► Store in plugin registry

Hook Execution
    │
    ▼
PluginManager.execute_hook(hook, context)
    │
    ├─► Find plugins subscribed to hook
    │
    ├─► For each plugin:
    │   ├─► Check if enabled
    │   ├─► Call plugin.on_hook(hook, context)
    │   └─► Update context with result
    │
    └─► Return final context

Application Shutdown
    │
    ▼
PluginManager.unload_all()
    │
    └─► For each plugin:
        └─► Call plugin.cleanup()
```

## Security Architecture

### Authentication

```
User Credentials
    │
    ▼
/auth/login
    │
    ├─► Verify password (bcrypt)
    │
    ├─► Generate JWT token
    │   ├─► Payload: {sub: user_id, username}
    │   ├─► Sign with SECRET_KEY
    │   └─► Set expiration
    │
    └─► Return token

Protected Endpoint
    │
    ▼
Authorization Header: Bearer {token}
    │
    ▼
get_current_user() dependency
    │
    ├─► Decode JWT token
    ├─► Verify signature
    ├─► Check expiration
    ├─► Load user from database
    ├─► Verify user is active
    │
    └─► Return user or raise 401
```

### API Key Authentication

```
Request with X-API-Key header
    │
    ▼
verify_api_key() dependency
    │
    ├─► Lookup API key in database
    ├─► Verify is_active
    ├─► Check expiration
    ├─► Update last_used_at
    │
    └─► Return API key or raise 401
```

## Scalability

### Horizontal Scaling

- **API Servers**: Multiple FastAPI instances behind load balancer
- **Celery Workers**: Scale workers based on queue length
- **Database**: PostgreSQL with read replicas
- **Redis**: Redis Cluster for high availability
- **MinIO**: Distributed MinIO cluster

### Caching Strategy

- **Redis**: Session data, rate limiting counters
- **Database**: Connection pooling, query result caching
- **HTTP**: Client-side caching with ETags

### Performance Optimizations

- Async database queries with asyncpg
- Batch inserts for bulk operations
- Connection pooling (database, HTTP, Redis)
- Rate limiting to prevent abuse
- Lazy loading of relationships
- Pagination for large result sets

## Monitoring and Observability

### Logging

- Structured logging with structlog
- Log levels: DEBUG, INFO, WARNING, ERROR
- Context: request_id, user_id, task_id
- Output: JSON for production, colored for development

### Metrics (Future)

- Prometheus metrics export
- Request duration histograms
- Error rate counters
- Queue length gauges
- Database connection pool metrics

### Tracing (Future)

- OpenTelemetry integration
- Distributed tracing across services
- Request flow visualization

## Deployment

### Docker Compose

```
┌─────────────────────────────────────────┐
│          Load Balancer / Nginx          │
└────┬────────────────────────────────┬───┘
     │                                │
┌────▼─────┐                    ┌────▼─────┐
│   API    │                    │   API    │
│ Instance │                    │ Instance │
└────┬─────┘                    └────┬─────┘
     │                                │
     └────────────┬───────────────────┘
                  │
     ┌────────────┼────────────┬──────────┐
     │            │            │          │
┌────▼─────┐┌────▼─────┐┌────▼─────┐┌───▼────┐
│PostgreSQL││  Redis   ││  MinIO   ││ Celery │
│          ││          ││          ││ Worker │
└──────────┘└──────────┘└──────────┘└────┬───┘
                                         │
                                    ┌────▼────┐
                                    │  Celery │
                                    │  Beat   │
                                    └─────────┘
```

### Environment Variables

- **Application**: DEBUG, SECRET_KEY, JWT_EXPIRATION
- **Database**: POSTGRES_*
- **Redis**: REDIS_*
- **MinIO**: MINIO_*
- **Celery**: BROKER_URL, RESULT_BACKEND

## Future Architecture Enhancements

1. **Event Sourcing**: Store all events for audit trail
2. **CQRS**: Separate read and write models
3. **GraphQL**: Alternative API with subscriptions
4. **gRPC**: High-performance service-to-service communication
5. **Service Mesh**: Istio for service discovery and routing
6. **Kubernetes**: Container orchestration
7. **Multi-tenancy**: Isolated data per organization
