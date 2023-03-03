import uuid
from datetime import datetime, timedelta
from django.utils import timezone

from django.test import testcases

from openbook_auth.models import User
from openbook_common.tests.helpers import make_user, make_notification


class LastSeenNotificationTests(testcases.TestCase):
    def test_when_notification_with_id_does_not_exist_nothing_happens(self):
        user = make_user()
        self.assertIsNone(user.last_seen_notification_timestamp)

        unknown_id = uuid.uuid4()
        user.store_last_seen_notification(unknown_id)

        self.assertIsNone(user.last_seen_notification_timestamp)

        timestamp = timezone.now() - timedelta(days=2)
        user.last_seen_notification_timestamp = timestamp

        user.store_last_seen_notification(unknown_id)

        self.assertEqual(user.last_seen_notification_timestamp, timestamp)

    def test_user_without_last_seen_notification_timestamp_always_gets_new_timestamp(self):
        user = make_user()
        notification = make_notification(user)

        new_timestamp = timezone.now()

        notification.created = new_timestamp
        notification.save()

        user.store_last_seen_notification(notification.id)

        self.assertEqual(user.last_seen_notification_timestamp, new_timestamp)

    def test_last_seen_timestamp_is_not_updated_when_older(self):
        user = make_user()
        notification = make_notification(user)

        newer_timestamp = timezone.now()
        older_timestamp = newer_timestamp - timedelta(seconds=10)

        user.last_seen_notification_timestamp = newer_timestamp
        notification.created = older_timestamp
        notification.save()

        user.store_last_seen_notification(notification.id)

        self.assertEqual(user.last_seen_notification_timestamp, newer_timestamp)

    def test_last_seen_timestamp_is_updated_when_newer(self):
        user = make_user()
        notification = make_notification(user)

        newer_timestamp = timezone.now()
        older_timestamp = newer_timestamp - timedelta(seconds=10)

        user.last_seen_notification_timestamp = older_timestamp
        notification.created = newer_timestamp
        notification.save()

        user.store_last_seen_notification(notification.id)

        self.assertEqual(user.last_seen_notification_timestamp, newer_timestamp)

    def test_last_received_timestamp_is_updated_when_empty_before(self):
        user = make_user()
        notification = make_notification(user)

        new_timestamp = timezone.now()

        notification.created = new_timestamp

        User.store_last_received_notification(user.id, notification)

        user = User.objects.get(id=user.id)
        self.assertEqual(user.last_received_notification_timestamp, new_timestamp)

    def test_last_received_timestamp_is_updated_when_newer(self):
        user = make_user()
        notification = make_notification(user)

        newer_timestamp = timezone.now()
        older_timestamp = newer_timestamp - timedelta(seconds=10)

        user.last_received_notification_timestamp = older_timestamp
        user.save()
        notification.created = newer_timestamp

        User.store_last_received_notification(user.id, notification)

        user = User.objects.get(id=user.id)
        self.assertEqual(user.last_received_notification_timestamp, newer_timestamp)

    def test_last_received_timestamp_is_not_updated_when_older(self):
        user = make_user()
        notification = make_notification(user)

        newer_timestamp = timezone.now()
        older_timestamp = newer_timestamp - timedelta(seconds=10)

        user.last_received_notification_timestamp = newer_timestamp
        user.save()
        notification.created = older_timestamp

        User.store_last_received_notification(user.id, notification)

        user = User.objects.get(id=user.id)
        self.assertEqual(user.last_received_notification_timestamp, newer_timestamp)
