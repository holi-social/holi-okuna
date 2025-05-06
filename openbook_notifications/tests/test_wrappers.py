from django.test import TestCase, override_settings

from openbook_common.tests.helpers import make_user
from openbook_notifications.wrappers import skip_e2e_notifications


@skip_e2e_notifications
def dummy_notification_function(user, *args, **kwargs):
    return "Notification sent"


class SkipTestNotificationsTests(TestCase):
    @override_settings(ENVIRONMENT_ID="staging")
    def test_skips_notification_for_e2e_email_in_staging(self):
        user = make_user(email="test@e2etest.com")
        result = dummy_notification_function(user)
        self.assertIsNone(result)

    @override_settings(ENVIRONMENT_ID="staging")
    def test_runs_notification_for_normal_email_in_staging(self):
        user = make_user(email="user@example.com")
        result = dummy_notification_function(user)
        self.assertEqual(result, "Notification sent")

    @override_settings(ENVIRONMENT_ID="production")
    def test_runs_notification_for_e2e_email_outside_staging(self):
        user = make_user(email="test@e2etest.com")
        result = dummy_notification_function(user)
        self.assertEqual(result, "Notification sent")

    @override_settings(ENVIRONMENT_ID="staging")
    def test_works_with_user_in_kwargs(self):
        user = make_user(email="test@e2etest.com")
        result = dummy_notification_function(somearg="hello", user=user)
        self.assertIsNone(result)

    @override_settings(ENVIRONMENT_ID="staging")
    def test_ignores_non_user_like_args(self):
        class NotUser:
            pass

        result = dummy_notification_function(NotUser())
        self.assertEqual(result, "Notification sent")
