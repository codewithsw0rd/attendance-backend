# This will be executed when Django starts up
from .celery import app as celery_app

__all__ = ('celery_app',)
