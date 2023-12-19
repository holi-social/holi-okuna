import pytest

from django.test import TestCase
from novu.api import MessageApi
from novu.dto import MessageDto, PaginatedMessageDto
from requests.exceptions import HTTPError
from unittest.mock import patch, call

from novu.api.event import EventApi
from novu.api.subscriber import SubscriberApi

from openbook_common.tests.helpers import make_user
from openbook_notifications.api import NotificationApi
from openbook_notifications.enums import NotificationProvider

from openbook_common.enums import FeatureToggleName, FeatureToggleType
from openbook_common.models import FeatureToggle as FeatureToggleModel


@pytest.mark.django_db
class NotificationApiTestCase(TestCase):
    def setUp(self):
        self.user = make_user(name="John", last_name="Doe")
        self.locale = "en"
        self.notifications_toggle = FeatureToggleModel.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )

    def tearDown(self):
        self.user.delete()

    @patch.object(SubscriberApi, "create")
    def test_create_subscriber(self, mock_subscriber_api_create):
        subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": str(self.user.username),
            "locale": self.locale,
        }
        mock_subscriber_api_create.return_value = subscriber_data

        subscriber = NotificationApi.create_subscriber(self.user, self.locale)

        self.assertEqual(subscriber, subscriber_data)

    @patch.object(SubscriberApi, "delete")
    def test_delete_subscriber(self, mock_subscriber_api_delete):
        subscriber_id = str(self.user.username)

        NotificationApi.delete_subscriber(subscriber_id)

        mock_subscriber_api_delete.assert_called_once_with(subscriber_id=subscriber_id)

    @patch.object(
        SubscriberApi, "delete", side_effect=HTTPError(response=type("Response", (object,), {"status_code": 404}))
    )
    def test_delete_subscriber_if_already_deleted(self, mock_subscriber_api_delete):
        subscriber_id = str(self.user.username)

        NotificationApi.delete_subscriber(subscriber_id)

        mock_subscriber_api_delete.assert_called_once_with(subscriber_id=subscriber_id)

    @patch.object(SubscriberApi, "get")
    def test_find_subscriber(self, mock_subscriber_api_get):
        subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": str(self.user.username),
            "locale": self.locale,
        }
        mock_subscriber_api_get.return_value = subscriber_data

        subscriber = NotificationApi.find_subscriber(self.user.username)

        self.assertEqual(subscriber, subscriber_data)

    @patch.object(SubscriberApi, "get")
    @patch.object(SubscriberApi, "create")
    def test_find_or_create_subscriber_existing(self, mock_subscriber_api_create, mock_subscriber_api_get):
        subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": str(self.user.username),
            "locale": self.locale,
        }
        mock_subscriber_api_get.return_value = subscriber_data

        subscriber = NotificationApi.find_or_create_subscriber(self.user, self.locale)

        self.assertEqual(subscriber, subscriber_data)
        mock_subscriber_api_create.assert_not_called()

    @patch.object(
        SubscriberApi, "get", side_effect=HTTPError(response=type("Response", (object,), {"status_code": 404}))
    )
    @patch.object(SubscriberApi, "create")
    def test_find_or_create_subscriber_not_existing(self, mock_subscriber_api_create, mock_subscriber_api_get):
        subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": str(self.user.username),
            "locale": self.locale,
        }

        mock_subscriber_api_create.return_value = subscriber_data

        subscriber = NotificationApi.find_or_create_subscriber(self.user, self.locale)

        self.assertEqual(subscriber, subscriber_data)
        mock_subscriber_api_get.assert_called_once()
        mock_subscriber_api_create.assert_called_once()

    @patch.object(SubscriberApi, "put")
    def test_update_subscriber(self, mock_subscriber_api_put):
        subscriber_data = {
            "subscriber_id": str(self.user.username),
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "locale": self.locale,
        }
        mock_subscriber_api_put.return_value = subscriber_data

        subscriber = NotificationApi.update_subscriber(self.user, self.locale)

        self.assertEqual(subscriber, subscriber_data)

    @patch.object(SubscriberApi, "put")
    @patch.object(SubscriberApi, "create")
    def test_create_or_update_subscriber_existing(self, mock_subscriber_api_create, mock_subscriber_api_put):
        subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": str(self.user.username),
            "locale": self.locale,
        }
        mock_subscriber_api_put.return_value = subscriber_data

        subscriber = NotificationApi.create_or_update_subscriber(self.user, self.locale)

        self.assertEqual(subscriber, subscriber_data)
        mock_subscriber_api_create.assert_not_called()

    @patch.object(
        SubscriberApi, "put", side_effect=HTTPError(response=type("Response", (object,), {"status_code": 404}))
    )
    @patch.object(SubscriberApi, "create")
    def test_create_or_update_subscriber_not_existing(self, mock_subscriber_api_create, mock_subscriber_api_put):
        subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": str(self.user.username),
            "locale": self.locale,
        }

        mock_subscriber_api_create.return_value = subscriber_data

        subscriber = NotificationApi.create_or_update_subscriber(self.user, self.locale)

        self.assertEqual(subscriber, subscriber_data)
        mock_subscriber_api_put.assert_called_once()
        mock_subscriber_api_create.assert_called_once()

    @patch.object(
        SubscriberApi, "put", side_effect=HTTPError(response=type("Response", (object,), {"status_code": 400}))
    )
    @patch.object(SubscriberApi, "create")
    def test_create_or_update_subscriber_not_existing_code_400(
        self, mock_subscriber_api_create, mock_subscriber_api_put
    ):
        subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": str(self.user.username),
            "locale": self.locale,
        }

        mock_subscriber_api_create.return_value = subscriber_data

        subscriber = NotificationApi.create_or_update_subscriber(self.user, self.locale)

        self.assertEqual(subscriber, subscriber_data)
        mock_subscriber_api_put.assert_called_once()
        mock_subscriber_api_create.assert_called_once()

    @patch.object(SubscriberApi, "credentials")
    @patch.object(SubscriberApi, "delete_credentials")
    def test_set_subscriber_credentials(self, mock_subscriber_api_delete_credentials, mock_subscriber_api_credentials):
        user_id = str(self.user.username)
        provider_id = NotificationProvider.APNS
        webhook_url = "https://example.com/webhook"
        device_tokens = ["test_device_token1", "test_device_token2"]

        expected_subscriber_data = {
            "first_name": self.user.profile.name,
            "last_name": self.user.profile.last_name,
            "avatar": self.user.profile.avatar.url if self.user.profile.avatar else None,
            "email": self.user.email,
            "subscriber_id": user_id,
            "locale": self.locale,
        }

        mock_subscriber_api_credentials.return_value = expected_subscriber_data

        response = NotificationApi.set_subscriber_credentials(user_id, provider_id, webhook_url, device_tokens)

        self.assertEqual(response, expected_subscriber_data)
        mock_subscriber_api_credentials.assert_called_once_with(
            user_id, provider_id.value.value, webhook_url, device_tokens
        )

    @patch.object(EventApi, "delete")
    def test_cancel_workflow(self, mock_event_api_delete):
        mock_event_api_delete.return_value = None

        NotificationApi.cancel_workflow(transaction_id="transaction-id")

        mock_event_api_delete.assert_called_once_with(transaction_id="transaction-id")

    @patch.object(MessageApi, "list")
    @patch.object(MessageApi, "delete")
    def test_delete_in_app_messages(self, mock_message_api_delete, mock_message_api_list):
        mock_message_api_list.return_value = PaginatedMessageDto(
            data=[MessageDto(_id=1), MessageDto(_id=2)],
            total_count=2,
            page_size=10,
        )
        NotificationApi.delete_in_app_messages(transaction_id="transaction-id")
        mock_message_api_list.assert_called_once_with(
            transaction_id="transaction-id", channel="in_app", subscriber_id=None
        )
        mock_message_api_delete.assert_has_calls([call(message_id=1), call(message_id=2)])

    @patch.object(MessageApi, "list")
    @patch.object(MessageApi, "delete")
    def test_delete_multiple_pages_of_in_app_messages(self, mock_message_api_delete, mock_message_api_list):
        mock_message_api_list.side_effect = [
            PaginatedMessageDto(
                data=[MessageDto(_id=1), MessageDto(_id=2)],
                total_count=3,
                page_size=2,
            ),
            PaginatedMessageDto(
                data=[MessageDto(_id=3)],
                total_count=1,
                page_size=2,
            ),
        ]

        # WHEN
        NotificationApi.delete_in_app_messages(transaction_id="transaction-id")

        # THEN
        mock_message_api_list.call_count == 2
        mock_message_api_delete.assert_has_calls([call(message_id=1), call(message_id=2), call(message_id=3)])

    @patch.object(MessageApi, "list")
    @patch.object(MessageApi, "delete")
    def test_delete_in_app_messages_for_subscriber(self, mock_message_api_delete, mock_message_api_list):
        subscriber_id = str(self.user.username)
        mock_message_api_list.return_value = PaginatedMessageDto(
            data=[MessageDto(_id=1), MessageDto(_id=2)],
            total_count=2,
            page_size=10,
        )
        NotificationApi.delete_in_app_messages(transaction_id="transaction-id", subscriber_id=subscriber_id)
        mock_message_api_list.assert_called_once_with(
            transaction_id="transaction-id", channel="in_app", subscriber_id=subscriber_id
        )
        mock_message_api_delete.assert_has_calls([call(message_id=1), call(message_id=2)])

    @patch.object(MessageApi, "list")
    @patch.object(
        MessageApi, "delete", side_effect=HTTPError(response=type("Response", (object,), {"status_code": 404}))
    )
    def test_delete_in_app_messages_if_already_deleted(self, mock_message_api_delete, mock_message_api_list):
        mock_message_api_list.return_value = PaginatedMessageDto(
            data=[MessageDto(_id=1)],
            total_count=1,
            page_size=10,
        )
        NotificationApi.delete_in_app_messages(transaction_id="transaction-id")
        mock_message_api_list.assert_called_once_with(
            transaction_id="transaction-id", channel="in_app", subscriber_id=None
        )
        mock_message_api_delete.assert_has_calls([call(message_id=1)])
