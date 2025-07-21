import json
import pytest
import base64

from django.test import AsyncClient, TransactionTestCase
from unittest import mock
from django.urls import reverse
from asgiref.sync import async_to_sync
from requests.exceptions import HTTPError
from novu.dto.subscriber import SubscriberDto
from rest_framework.authtoken.models import Token
from semver import Version

from favorites.events import IncomingEvent
from openbook_auth.models import User
from openbook_notifications.payloads import NotificationType

from openbook_common.tests.helpers import make_user, make_community


@pytest.mark.django_db
class OryWebhookTestCase(TransactionTestCase):
    @mock.patch("openbook_notifications.api.NotificationApi.update_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.find_subscriber")
    def test_updates_user_email(self, mock_find_subscriber, mock_update_subscriber):
        # GIVEN
        client = AsyncClient()
        user = make_user()
        token = Token.objects.first().key
        new_email = "new_email@test.com"
        payload = {
            "id": user.username,
            "email": new_email,
        }
        endpoint = reverse("ory-webhook-endpoint")
        locale = "en"
        mock_find_subscriber.return_value = SubscriberDto(subscriber_id=user.username, locale=locale)

        # WHEN
        response = async_to_sync(client.post)(
            endpoint, payload, content_type="application/json", headers={"AUTHORIZATION": "Token " + token}
        )

        # THEN
        assert response.status_code == 200

        updated_user = User.objects.get(username=user.username)
        assert updated_user.email == new_email

        mock_find_subscriber.assert_called_with(user_id=user.username)
        mock_update_subscriber.assert_called_with(user=updated_user, locale=locale)

    @mock.patch("openbook_notifications.api.NotificationApi.update_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.find_subscriber")
    def test_does_not_update_email_in_novu_without_subscriber(self, mock_find_subscriber, mock_update_subscriber):
        # GIVEN
        client = AsyncClient()
        user = make_user()
        token = Token.objects.first().key
        new_email = "new_email@test.com"
        payload = {
            "id": user.username,
            "email": new_email,
        }
        endpoint = reverse("ory-webhook-endpoint")
        mock_find_subscriber.side_effect = HTTPError(response=type("Response", (object,), {"status_code": 404}))

        # WHEN
        response = async_to_sync(client.post)(
            endpoint, payload, content_type="application/json", headers={"AUTHORIZATION": "Token " + token}
        )

        # THEN
        assert response.status_code == 200

        updated_user = User.objects.get(username=user.username)
        assert updated_user.email == new_email

        mock_find_subscriber.assert_called_with(user_id=user.username)
        mock_update_subscriber.assert_not_called()

    @mock.patch("openbook_notifications.api.NotificationApi.update_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.find_subscriber")
    def test_throws_error_when_updating_novu_subscriber(self, mock_find_subscriber, mock_update_subscriber):
        # GIVEN
        client = AsyncClient()
        user = make_user()
        token = Token.objects.first().key
        new_email = "new_email@test.com"
        payload = {
            "id": user.username,
            "email": new_email,
        }
        endpoint = reverse("ory-webhook-endpoint")
        mock_find_subscriber.side_effect = HTTPError(response=type("Response", (object,), {"status_code": 500}))

        # WHEN
        with self.assertRaises(HTTPError):
            async_to_sync(client.post)(
                endpoint, payload, content_type="application/json", headers={"AUTHORIZATION": "Token " + token}
            )

        # THEN
        updated_user = User.objects.get(username=user.username)
        assert updated_user.email == new_email

        mock_find_subscriber.assert_called_with(user_id=user.username)
        mock_update_subscriber.assert_not_called()


@pytest.mark.django_db
class NotificationWebhookTestCase(TransactionTestCase):
    def test_checks_if_subscriber_is_admin_for_membership_request(self):
        # GIVEN
        client = AsyncClient()
        user = make_user()
        space = make_community(creator=user)
        payload = {
            "subscriber": {
                "subscriberId": user.username,
            },
            "payload": {
                "notificationType": NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
                "data": {"space": {"name": space.name}},
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["valid"] is True

    def test_handles_if_subscriber_is_not_admin_for_membership_request(self):
        # GIVEN
        client = AsyncClient()
        user = make_user()
        space = make_community()
        payload = {
            "subscriber": {
                "subscriberId": user.username,
            },
            "payload": {
                "notificationType": NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
                "data": {"space": {"name": space.name}},
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["valid"] is False

    def test_handles_missing_user_for_membership_request(self):
        # GIVEN
        client = AsyncClient()
        space = make_community()
        payload = {
            "subscriber": {
                "subscriberId": "unknown",
            },
            "payload": {
                "notificationType": NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
                "data": {"space": {"name": space.name}},
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["valid"] is False

    def test_handles_missing_space_for_membership_request(self):
        # GIVEN
        client = AsyncClient()
        user = make_user()
        payload = {
            "subscriber": {
                "subscriberId": user.username,
            },
            "payload": {
                "notificationType": NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
                "data": {"space": {"name": "unknown"}},
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["valid"] is False

    def test_handles_invalid_notification_payload_for_membership_request(self):
        # GIVEN
        client = AsyncClient()
        user = make_user()
        payload = {
            "subscriber": {
                "subscriberId": user.username,
            },
            "payload": {
                "notificationType": NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
                "data": {},
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["valid"] is False

    def test_handles_invalid_payload_for_membership_request(self):
        # GIVEN
        client = AsyncClient()
        make_user()
        payload = {
            "payload": {
                "notificationType": NotificationType.SPACE_MEMBERSHIP_REQUEST.value,
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["valid"] is False

    def test_handles_unhandled_notification_type(self):
        # GIVEN
        client = AsyncClient()
        make_user()
        payload = {
            "payload": {
                "notificationType": NotificationType.SPACE_MEMBERSHIP_INVITE.value,
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 400

    def test_handles_unknown_notification_type(self):
        # GIVEN
        client = AsyncClient()
        make_user()
        payload = {
            "payload": {
                "notificationType": "unknown",
            },
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 400

    def test_handles_missing_notification_type(self):
        # GIVEN
        client = AsyncClient()
        make_user()
        payload = {
            "payload": {},
        }
        endpoint = reverse("notification-webhook-endpoint")

        # WHEN
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # THEN
        assert response.status_code == 400


@pytest.mark.django_db
class PubSubPushEndpointEventHandlingTestCase(TransactionTestCase):
    @mock.patch("favorites.events.ExternalDataEventHandler.handle")
    def test_handles_events_for_external_data_topic(self, mock_handle):
        client = AsyncClient()
        event_data = {"eventType": "VolunteeringDeleted", "eventVersion": "1.0.0", "data": {"id": "volunteering_123"}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}

        # works with external-data-staging topic
        staging_endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data-staging"})
        response = async_to_sync(client.post)(staging_endpoint, payload, content_type="application/json")

        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["status"] == "OK"
        mock_handle.assert_called_with(
            IncomingEvent(
                event_type="VolunteeringDeleted", event_version=Version.parse("1.0.0"), data={"id": "volunteering_123"}
            )
        )
        mock_handle.reset_mock()

        # works with external-data-production topic
        production_endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data-production"})
        response = async_to_sync(client.post)(production_endpoint, payload, content_type="application/json")

        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["status"] == "OK"
        mock_handle.assert_called_with(
            IncomingEvent(
                event_type="VolunteeringDeleted", event_version=Version.parse("1.0.0"), data={"id": "volunteering_123"}
            )
        )

    def test_responds_400_for_unknown_topics(self):
        client = AsyncClient()
        event_data = {"eventType": "VolunteeringDeleted", "eventVersion": "1.0.0", "data": {"id": "volunteering_456"}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}
        endpoint = reverse("pubsub_push", kwargs={"topic_name": "unknown-topic"})

        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        assert response.status_code == 400
        content = json.loads(response.content)
        assert "Unhandled topic: unknown-topic" in content["message"]

    def test_ignores_unknown_event_types_gracefully(self):
        client = AsyncClient()
        event_data = {"eventType": "UnknownEventType", "eventVersion": "1.0.0", "data": {"id": "someRecord"}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}
        endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data"})

        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        assert response.status_code == 200
