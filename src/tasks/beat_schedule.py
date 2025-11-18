"""Celery Beat periodic task schedule."""

from celery.schedules import crontab

# Periodic task schedule
beat_schedule = {
    # Retry failed webhooks every minute
    "retry-failed-webhooks": {
        "task": "retry_failed_webhooks",
        "schedule": 60.0,  # Every 60 seconds
        "options": {
            "expires": 55.0,  # Expire after 55 seconds to avoid overlap
        },
    },
    # Clean up old webhook deliveries every day at 2 AM
    "cleanup-old-webhook-deliveries": {
        "task": "cleanup_old_deliveries",
        "schedule": crontab(hour=2, minute=0),
        "options": {
            "expires": 3600,  # Expire after 1 hour
        },
    },
    # Update case statistics every hour
    "update-case-statistics": {
        "task": "update_case_statistics",
        "schedule": crontab(minute=0),  # Every hour
        "options": {
            "expires": 3300,  # Expire after 55 minutes
        },
    },
    # Check for stuck scraping tasks every 15 minutes
    "check-stuck-tasks": {
        "task": "check_stuck_tasks",
        "schedule": 900.0,  # Every 15 minutes
        "options": {
            "expires": 840.0,  # Expire after 14 minutes
        },
    },
    # Cleanup expired sessions every day at 3 AM
    "cleanup-expired-sessions": {
        "task": "cleanup_expired_sessions",
        "schedule": crontab(hour=3, minute=0),
        "options": {
            "expires": 3600,
        },
    },
}
