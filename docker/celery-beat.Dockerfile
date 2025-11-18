FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml ./

# Install uv and dependencies
RUN pip install uv && \
    uv pip install --system -e .

# Copy application
COPY . .

# Run Celery Beat
CMD ["celery", "-A", "src.tasks.celery_app", "beat", "--loglevel=info"]
