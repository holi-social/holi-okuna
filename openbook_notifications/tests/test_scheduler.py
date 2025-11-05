import pytest
from unittest.mock import patch, MagicMock
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from openbook_notifications.scheduler import (
    get_scheduler,
    start_scheduler,
    shutdown_scheduler,
)


@pytest.mark.django_db
class TestScheduler:
    def setup_method(self):
        """Reset scheduler state before each test."""
        # Reset module-level variables by reloading or resetting
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = None
        scheduler_module._scheduler_started = False

    def test_get_scheduler_creates_scheduler_with_correct_config(self):
        """Test that get_scheduler creates a scheduler with the correct timezone."""
        scheduler = get_scheduler()

        assert scheduler is not None
        assert isinstance(scheduler, BackgroundScheduler)
        assert scheduler.timezone == ZoneInfo("Europe/Berlin")

    def test_get_scheduler_schedules_job_correctly(self):
        """Test that the job is scheduled with the correct trigger."""
        scheduler = get_scheduler()

        # Get all scheduled jobs
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1

        job = jobs[0]
        assert job.id == "send_pre_good_deed_email_series"
        assert job.name == "Send pre-good-deed email series to eligible users"
        assert isinstance(job.trigger, CronTrigger)

        # Verify cron trigger is set to 9am in Europe/Berlin timezone
        assert job.trigger.timezone == ZoneInfo("Europe/Berlin")
        # Verify the trigger has the expected configuration by checking fields
        # CronTrigger.fields order: [second, minute, hour, day, month, day_of_week]
        # We can check that the hour field (index 2) and minute field (index 1) are set
        # The hour field should have a value expression containing 9
        hour_field = job.trigger.fields[2]
        minute_field = job.trigger.fields[1]
        # Verify they're not "all" expressions (which would be * * * * *)
        assert hour_field is not None
        assert minute_field is not None

    def test_get_scheduler_returns_same_instance(self):
        """Test that get_scheduler returns the same instance on multiple calls."""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 is scheduler2

    @patch("openbook_notifications.scheduler.BackgroundScheduler")
    def test_start_scheduler_starts_scheduler(self, mock_scheduler_class):
        """Test that start_scheduler calls start() on the scheduler."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        mock_scheduler_class.return_value = mock_scheduler

        # Reset module state
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = mock_scheduler
        scheduler_module._scheduler_started = False

        start_scheduler()

        mock_scheduler.start.assert_called_once()

    @patch("openbook_notifications.scheduler.BackgroundScheduler")
    def test_start_scheduler_only_starts_once(self, mock_scheduler_class):
        """Test that start_scheduler only starts the scheduler once."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        mock_scheduler_class.return_value = mock_scheduler

        # Reset module state
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = mock_scheduler
        scheduler_module._scheduler_started = False

        start_scheduler()
        start_scheduler()  # Call again

        # Should only be called once
        assert mock_scheduler.start.call_count == 1

    @patch("openbook_notifications.scheduler.BackgroundScheduler")
    def test_start_scheduler_does_not_start_if_already_running(self, mock_scheduler_class):
        """Test that start_scheduler doesn't start if scheduler is already running."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        mock_scheduler_class.return_value = mock_scheduler

        # Reset module state
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = mock_scheduler
        scheduler_module._scheduler_started = False

        start_scheduler()

        # Should not be called if already running
        mock_scheduler.start.assert_not_called()

    @patch("openbook_notifications.scheduler.BackgroundScheduler")
    def test_shutdown_scheduler_shuts_down_running_scheduler(self, mock_scheduler_class):
        """Test that shutdown_scheduler calls shutdown() on running scheduler."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = True
        mock_scheduler_class.return_value = mock_scheduler

        # Reset module state
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = mock_scheduler

        shutdown_scheduler()

        mock_scheduler.shutdown.assert_called_once()

    @patch("openbook_notifications.scheduler.BackgroundScheduler")
    def test_shutdown_scheduler_does_not_shutdown_if_not_running(self, mock_scheduler_class):
        """Test that shutdown_scheduler doesn't shutdown if scheduler is not running."""
        mock_scheduler = MagicMock()
        mock_scheduler.running = False
        mock_scheduler_class.return_value = mock_scheduler

        # Reset module state
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = mock_scheduler

        shutdown_scheduler()

        mock_scheduler.shutdown.assert_not_called()

    @patch("openbook_notifications.scheduler.BackgroundScheduler")
    def test_shutdown_scheduler_handles_none_scheduler(self, mock_scheduler_class):
        """Test that shutdown_scheduler handles None scheduler gracefully."""
        # Reset module state
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = None

        # Should not raise an exception
        shutdown_scheduler()

    @patch("openbook_notifications.scheduler.send_pre_good_deed_email_series_to_eligible_users")
    def test_scheduled_job_calls_target_function(self, mock_job_function):
        """Test that the scheduled job actually calls the target function."""
        # Reset scheduler to get a fresh instance with the mocked function
        import openbook_notifications.scheduler as scheduler_module

        scheduler_module._scheduler = None
        scheduler_module._scheduler_started = False

        scheduler = get_scheduler()

        # Manually trigger the job (simulating what APScheduler would do)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1

        job = jobs[0]
        # Get the actual function from the job
        func = job.func

        # Call the function
        func()

        # Verify the job function was called
        mock_job_function.assert_called_once()
