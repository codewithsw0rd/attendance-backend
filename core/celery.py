"""
Celery configuration for the Attendance System.
Handles async task queue and periodic scheduling.
"""
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('attendance_system')

# Load configuration from Django settings with namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# ────────────────────────────────────────────────────────────────────────────
# CELERY BEAT SCHEDULE (Periodic Tasks)
# ────────────────────────────────────────────────────────────────────────────

app.conf.beat_schedule = {
    # Auto-start sessions every minute
    # Checks for templates scheduled for current day/time and starts sessions
    'auto-start-sessions-every-minute': {
        'task': 'attendance.tasks.auto_start_sessions',
        'schedule': crontab(minute='*'),  # Every minute
    },
}
