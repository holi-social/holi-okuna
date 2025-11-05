import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from openbook_notifications.jobs import send_pre_good_deed_email_series_to_eligible_users

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None
_scheduler_started = False


def get_scheduler():
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=ZoneInfo("Europe/Berlin"))
        _scheduler.add_job(
            send_pre_good_deed_email_series_to_eligible_users,
            trigger=CronTrigger(hour=9, minute=0, timezone=ZoneInfo("Europe/Berlin")),
            id="send_pre_good_deed_email_series",
            name="Send pre-good-deed email series to eligible users",
            replace_existing=True,
        )
    return _scheduler


def start_scheduler():
    """Start APScheduler with configured jobs."""
    global _scheduler_started
    if _scheduler_started:
        return

    scheduler = get_scheduler()

    if not scheduler.running:
        logger.info("Starting APScheduler...")
        scheduler.start()
        _scheduler_started = True
        logger.info("APScheduler started. Jobs scheduled.")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        logger.info("Shutting down APScheduler...")
        _scheduler.shutdown()
        logger.info("APScheduler shutdown complete.")
