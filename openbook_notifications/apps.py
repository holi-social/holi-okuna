import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class OpenbookNotificationsConfig(AppConfig):
    name = "openbook_notifications"

    def ready(self):
        """Start APScheduler when Django is ready."""
        # Only start scheduler in the main process (not in migrations, tests, etc.)
        # Check if we're running in a command that shouldn't start the scheduler
        import sys

        # Skip scheduler for migrations, test commands, shell, etc.
        if any(arg in sys.argv for arg in ["migrate", "makemigrations", "test", "shell", "collectstatic", "flush"]):
            return

        # Also check if we're in a worker process (if you have workers)
        # You can add an environment variable check if needed

        try:
            from openbook_notifications.scheduler import start_scheduler

            start_scheduler()
        except Exception as e:
            logger.error(f"Failed to start APScheduler: {e}", exc_info=True)
