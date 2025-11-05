import uuid
from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest import mock
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.test import TestCase
from django.utils import timezone
from novu.api import EventApi

from openbook_common.tests.helpers import (
    make_community,
    make_community_task,
    make_feed_post_good_deed_category,
    make_user,
)
from openbook_notifications.jobs import send_pre_good_deed_email_series_to_eligible_users
from openbook_notifications.services import NotificationsService


@pytest.fixture(scope="class", autouse=True)
def mock_novu_api():
    with mock.patch.object(EventApi, "trigger"):
        # prevent sending novu notifications
        yield


@pytest.mark.django_db
class TestPreGoodDeedNotificationService(TestCase):
    def test_service_sends_notification(self):
        user = make_user()
        token = str(uuid.uuid4())

        with patch.object(EventApi, "trigger") as trigger_mock:
            NotificationsService.send_pre_good_deed_email_series_notification(user=user, token=token)
            assert trigger_mock.call_count == 1


@pytest.mark.django_db
class TestPreGoodDeedEmailJob(TestCase):
    def _berlin_yesterday_bounds_utc(self):
        berlin = ZoneInfo("Europe/Berlin")
        yesterday = timezone.localdate() - timedelta(days=1)
        start_local = datetime.combine(yesterday, time.min)
        end_local = start_local + timedelta(days=1)
        start_aware_local = timezone.make_aware(start_local, berlin)
        end_aware_local = timezone.make_aware(end_local, berlin)
        return (
            start_aware_local.astimezone(dt_timezone.utc),
            end_aware_local.astimezone(dt_timezone.utc),
            start_aware_local,
            end_aware_local,
        )

    def test_job_sends_only_to_eligible_users(self):
        start_utc, end_utc, _, _ = self._berlin_yesterday_bounds_utc()

        # Helper to place a user's join time
        def joined(dt):
            u = make_user()
            u.date_joined = dt
            u.save(update_fields=["date_joined"])
            return u

        # In-window eligible
        eligible = joined(start_utc + timedelta(hours=3))

        # In-window with good-deed post
        has_good_deed = joined(start_utc + timedelta(hours=4))
        good_deed_category = make_feed_post_good_deed_category()
        from feed_posts.models import FeedPost

        FeedPost.objects.create(
            creator=has_good_deed,
            description="did good",
            slug=str(uuid.uuid4()),
            category=good_deed_category,
        )

        # In-window with volunteering opportunity
        has_vo = joined(start_utc + timedelta(hours=5))
        from volunteering.models import VolunteeringOpportunityStatus, Status as VOStatus

        VolunteeringOpportunityStatus.objects.create(
            external_volunteering_opportunity_id=str(uuid.uuid4()),
            user=has_vo,
            status=VOStatus.TO_DO.value,
        )

        # In-window with completed task
        has_completed_task = joined(start_utc + timedelta(hours=6))
        from openbook_communities.models.completed_task import CompletedTask

        space_creator = make_user()
        community = make_community(creator=space_creator)
        task = make_community_task(community=community, creator=space_creator)

        CompletedTask.objects.create(task=task, user=has_completed_task)

        # Outside window (future)
        outside = joined(end_utc + timedelta(hours=1))

        with patch.object(EventApi, "trigger") as trigger_mock:
            msg = send_pre_good_deed_email_series_to_eligible_users()

        # Only the eligible user should receive a notification
        assert trigger_mock.call_count == 1
        # Sanity check: message mentions 1 user (handles both singular and plural)
        assert "1" in msg and "user" in msg.lower()
