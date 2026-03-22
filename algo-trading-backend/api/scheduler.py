"""
scheduler.py - Module-level APScheduler instance shared across the FastAPI app.

The scheduler is started in the FastAPI lifespan and is used by the live
trading router to add / remove per-symbol cron jobs.

Import::

    from api.scheduler import scheduler
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
