import uuid
from datetime import timedelta
from django.utils import timezone

from django.test import testcases

from openbook_common.tests.helpers import make_user, make_notification
from openbook_notifications.models import Notification


class LastSeenNotificationTests(testcases.TestCase):
    def test_when_notification_with_id_does_not_exist_nothing_happens(self):
        user = make_user()
        assert user.last_seen_notification_timestamp is None

        unknown_id = uuid.uuid4()
        user.store_last_seen_notification(unknown_id)

        assert user.last_seen_notification_timestamp is None

        timestamp = timezone.now() - timedelta(days=2)
        user.last_seen_notification_timestamp = timestamp

        user.store_last_seen_notification(unknown_id)

        assert user.last_seen_notification_timestamp == timestamp

    def test_user_without_last_seen_notification_timestamp_always_gets_new_timestamp(self):
        user = make_user()
        notification = make_notification(user)
        assert not notification.read

        new_timestamp = timezone.now()

        notification.created = new_timestamp
        notification.save()

        user.store_last_seen_notification(notification.id)

        assert user.last_seen_notification_timestamp == new_timestamp
        assert Notification.objects.get(id=notification.id).read

    def test_last_seen_timestamp_is_not_updated_when_older(self):
        user = make_user()
        notification = make_notification(user)
        assert not notification.read

        newer_timestamp = timezone.now()
        older_timestamp = newer_timestamp - timedelta(seconds=10)

        user.last_seen_notification_timestamp = newer_timestamp
        notification.created = older_timestamp
        notification.save()

        user.store_last_seen_notification(notification.id)

        assert user.last_seen_notification_timestamp == newer_timestamp
        # when the last_seen_timestamp is not updated, the read status is also not changed.
        assert not Notification.objects.get(id=notification.id).read

    def test_last_seen_timestamp_is_updated_when_newer(self):
        user = make_user()
        notification = make_notification(user)

        newer_timestamp = timezone.now()
        older_timestamp = newer_timestamp - timedelta(seconds=10)

        user.last_seen_notification_timestamp = older_timestamp
        notification.created = newer_timestamp
        notification.save()

        user.store_last_seen_notification(notification.id)

        assert user.last_seen_notification_timestamp == newer_timestamp
        assert Notification.objects.get(id=notification.id).read
