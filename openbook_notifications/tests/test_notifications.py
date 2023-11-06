import uuid
import pytest

from unittest.mock import call, patch
from django.test import TestCase

from requests import Session
from requests.adapters import HTTPAdapter

from novu.api import EventApi

from openbook_notifications.notifications import (
    Notification,
    SpaceMembershipRequestNotification,
    Workflow,
    SpaceMembershipRequestApprovalUserNotification,
    SpaceMembershipRequestDeclineUserNotification,
    SpaceMembershipRequestDeclineAdminNotification,
)
from openbook_notifications.payloads import (
    NotificationType,
    SpaceMembershipRequestPayload,
    SpaceMembershipRequestApprovalUserPayload,
    SpaceMembershipRequestDeclinePayload,
)
from openbook_common.tests.helpers import (
    make_community,
    make_user,
)
from openbook_common.enums import FeatureToggleName, FeatureToggleType
from openbook_common.models import FeatureToggle as FeatureToggleModel


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
        cls.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

        cls.overrides = {
            "type": "data",
            "fcm": {"type": "data", "data": {"key": "value"}},
            "apns": {"payload": {"data": {"key": "value"}}},
        }

    @patch.object(EventApi, "trigger")
    def test_notification_send(self, mock_event_api_trigger):
        result = self.notification_instance.send()

        # Assert that the EventApi trigger was called with the expected arguments
        mock_event_api_trigger.assert_called_with(
            name="test-workflow",
            recipients=["user-id"],
            payload={"data": {"key": "value"}},
            overrides=self.overrides,
            transaction_id="test-transaction-id",
        )

        self.assertEqual(result, mock_event_api_trigger.return_value)

    def test_notification_session_setup(self):
        # Test that the session is set up correctly
        self.assertIsInstance(self.notification_instance.session, Session)

        # Check the session's mounted adapter
        self.assertIsInstance(self.notification_instance.session.adapters["https://"], HTTPAdapter)

        # Check the adapter's attributes
        self.assertEqual(self.notification_instance.session.adapters["https://"].max_retries.total, 5)
        self.assertEqual(self.notification_instance.session.adapters["https://"].max_retries.backoff_factor, 1)
        self.assertEqual(
            self.notification_instance.session.adapters["https://"].max_retries.status_forcelist, [502, 503, 504]
        )

    @patch.object(EventApi, "trigger")
    def test_notification_send_with_retry(self, mock_event_api_trigger):
        # Simulate a failing first call
        mock_event_api_trigger.side_effect = [Exception("Failed"), {"status": "503"}]

        with self.assertRaises(Exception):
            self.notification_instance.send()

        self.notification_instance.send()

        # Assert that the EventApi trigger was called twice with the expected arguments
        assert mock_event_api_trigger.call_count == 2

        mock_event_api_trigger.assert_has_calls(
            [
                call(
                    name="test-workflow",
                    recipients=["user-id"],
                    payload={"data": {"key": "value"}},
                    overrides=self.overrides,
                    transaction_id="test-transaction-id",
                ),
                call(
                    name="test-workflow",
                    recipients=["user-id"],
                    payload={"data": {"key": "value"}},
                    overrides=self.overrides,
                    transaction_id="test-transaction-id",
                ),
            ]
        )


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


@pytest.mark.django_db
class SpaceMembershipRequestApprovalUserNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        approver = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestApprovalUserPayload(user=user, space=space, approver=approver)
        cls.notification_instance = SpaceMembershipRequestApprovalUserNotification(
            recipient=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_approval_user_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST_APPROVAL_USER.value)


@pytest.mark.django_db
class SpaceMembershipRequestDeclineUserNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        denier = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestDeclinePayload(
            user=user,
            space=space,
            denier=denier,
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_DECLINE_USER.value,
        )
        cls.notification_instance = SpaceMembershipRequestDeclineUserNotification(
            recipient=str(user.username),
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_decline_user_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST_DECLINE_USER.value)


@pytest.mark.django_db
class SpaceMembershipRequestDeclineAdminNotificationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = make_user()
        denier = make_user()
        space = make_community()
        transaction_id = str(uuid.uuid4())
        payload = SpaceMembershipRequestDeclinePayload(
            user=user,
            space=space,
            denier=denier,
            notification_type=NotificationType.SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN.value,
        )
        cls.notification_instance = SpaceMembershipRequestDeclineAdminNotification(
            recipients=[str(denier.username)],
            payload=payload,
            transaction_id=transaction_id,
        )

    def test_space_membership_request_decline_admin_notification_workflow(self):
        self.assertEqual(self.notification_instance.workflow, Workflow.SPACE_MEMBERSHIP_REQUEST_DECLINE_ADMIN.value)
