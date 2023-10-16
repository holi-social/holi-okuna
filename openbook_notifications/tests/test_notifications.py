import pytest

from unittest.mock import Mock, patch
from django.test import TestCase

from requests import Session
from requests.adapters import HTTPAdapter

from openbook_notifications.notifications import Notification
from openbook_notifications.toggles import notifications_toggle


@pytest.mark.django_db
class NotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.notification_instance = Notification(
            workflow="test-workflow",
            recipients=["user-id"],
            payload={"key": "value"},
        )

    @patch("novu.api.EventApi")
    @notifications_toggle
    def test_notification_send(self, mock_event_api):
        # Mock EventApi to prevent actual API calls
        mock_event_instance = Mock()
        mock_event_api.return_value = mock_event_instance

        result = self.notification_instance.send()

        # Assert that the EventApi trigger was called with the expected arguments
        mock_event_instance.trigger.assert_called_with(
            name="test-workflow",
            recipients=["user-id"],
            payload={"key": "value"},
        )

        self.assertEqual(result, mock_event_instance.trigger.return_value)

    def test_notification_session_setup(self):
        # Test that the session is set up correctly
        self.assertIsInstance(self.notification_instance.session, Session)

        # Check the session's monted adapter
        self.assertIsInstance(self.notification_instance.session.adapters["https://"], HTTPAdapter)

        # Check the adapter's attributes
        self.assertEqual(self.notification_instance.session.adapters["https://"].max_retries.total, 5)
        self.assertEqual(self.notification_instance.session.adapters["https://"].max_retries.backoff_factor, 1)
        self.assertEqual(
            self.notification_instance.session.adapters["https://"].max_retries.status_forcelist, [502, 503, 504]
        )
