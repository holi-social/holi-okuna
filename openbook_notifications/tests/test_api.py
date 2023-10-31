import pytest

from django.test import TestCase
from requests.exceptions import HTTPError
from unittest.mock import patch

from novu.api.subscriber import SubscriberApi

from openbook_common.tests.helpers import make_user
from openbook_notifications.api import NotificationApi  # Replace 'your_app_name' with your actual app name
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
        mock_subscriber_api_delete_credentials.assert_called_once_with(user_id, provider_id.value)
        mock_subscriber_api_credentials.assert_called_once_with(
            user_id, provider_id.value.value, webhook_url, device_tokens
        )
