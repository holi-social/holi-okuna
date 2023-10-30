import uuid
import pytest

from unittest.mock import Mock, call, patch
from django.test import TestCase

from requests import Session
from requests.adapters import HTTPAdapter

from openbook_notifications.notifications import Notification, SpaceMembershipRequestNotification, Workflow
from openbook_notifications.payloads import SpaceMembershipRequestPayload
from openbook_notifications.toggles import notifications_toggle
from openbook_common.tests.helpers import (
    make_community,
    make_user,
)


@pytest.mark.django_db
class NotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.notification_instance = Notification(
            workflow="test-workflow",
            recipients=["user-id"],
            payload={"data": {"key": "value"}},
            transaction_id="test-transaction-id",
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
            payload={"data": {"key": "value"}},
            overrides={
                "type": "data",
                "fcm": {"type": "data", "data": {"key: value"}},
                "apns": {"payload": {"data": {"key: value"}}},
            },
            transaction_id="test-transaction-id",
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

    @patch("novu.api.EventApi")
    @notifications_toggle
    def test_notification_send_with_retry(self, mock_event_api):
        mock_event_instance = Mock()
        mock_event_api.return_value = mock_event_instance

        # Simulate a failing first call
        mock_event_instance.trigger.side_effect = [Exception("Failed"), {"status": "503"}]

        result = self.notification_instance.send()

        # Assert that the EventApi trigger was called twice with the expected arguments
        mock_event_instance.trigger.assert_has_calls(
            [
                call(name="test-workflow", recipients=["user-id"], payload={"data": {"key": "value"}}),
                call(name="test-workflow", recipients=["user-id"], payload={"data": {"key": "value"}}),
            ]
        )

        self.assertEqual(result, {"status": "success"})


@pytest.mark.django_db
class SpaceMembershipRequestNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestPayload(user=user, space=space)
        cls.notification_instance = SpaceMembershipRequestNotification(
            recipients=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST.value)
