import json
import pytest
import base64

from django.test import AsyncClient, TransactionTestCase
from unittest import mock
from django.urls import reverse
from asgiref.sync import async_to_sync

from favorites.models import UserFavorite, FavoritableType, ExternalVolunteeringOpportunity
from django.contrib.contenttypes.models import ContentType

from openbook_common.tests.helpers import make_user


@pytest.mark.django_db
class PubSubPushEndpointFavoritesSyncingTestCase(TransactionTestCase):
    # authentication logic is skipped when is_development, which simplifies the testing here
    @mock.patch("openbook.webhooks.environment_checker.is_development", return_value=True)
    @mock.patch("favorites.models.UserFavorite.delete_all_favorites_for_external_volunteering_opportunity")
    def test_handles_volunteering_deleted_event_for_external_data_topic(self, mock_delete_favorites, mock_is_dev):
        client = AsyncClient()
        record_id = "test-record-id"
        event_data = {"eventType": "VolunteeringDeleted", "eventVersion": "1.0.0", "data": {"id": record_id}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}
        endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data"})

        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["status"] == "OK"

        # and delete_all_favorites_for_external_volunteering_opportunity method was called
        mock_delete_favorites.assert_called_once_with(record_id)

    @mock.patch("openbook.webhooks.environment_checker.is_development", return_value=True)
    def test_handles_unknown_topic(self, mock_is_dev):
        client = AsyncClient()
        record_id = "test-record-id"
        event_data = {"eventType": "VolunteeringDeleted", "eventVersion": "1.0.0", "data": {"id": record_id}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}
        endpoint = reverse("pubsub_push", kwargs={"topic_name": "unknown-topic"})

        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        assert response.status_code == 400

    @mock.patch("openbook.webhooks.environment_checker.is_development", return_value=True)
    def test_ignores_unknown_event_types_gracefully(self, mock_is_dev):
        client = AsyncClient()
        event_data = {"eventType": "UnknownEventType", "eventVersion": "1.0.0", "data": {}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}
        endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data"})

        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        assert response.status_code == 200

    @mock.patch("openbook.webhooks.environment_checker.is_development", return_value=True)
    def test_handles_missing_record_id(self, mock_is_dev):
        client = AsyncClient()
        event_data = {"eventType": "VolunteeringDeleted", "eventVersion": "1.0.0", "data": {}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}
        endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data"})

        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        assert response.status_code == 500
        content = json.loads(response.content)
        assert "Event not handled" in content["message"]

    @mock.patch("openbook.webhooks.environment_checker.is_development", return_value=True)
    def test_integration_with_user_favorite_model(self, mock_is_dev):
        # given a favorite for the external volunteering opportunity
        client = AsyncClient()
        user = make_user()
        record_id = "test-record-id"

        favoritable_type = ContentType.objects.get(model=FavoritableType.EXTERNAL_VOLUNTEERING_OPPORTUNITY.value)
        ExternalVolunteeringOpportunity.objects.create(external_id=record_id)
        UserFavorite.objects.create(user=user, favoritable_id=record_id, favoritable_type=favoritable_type)

        assert UserFavorite.objects.filter(
            user=user, favoritable_id=record_id, favoritable_type=favoritable_type
        ).exists()

        # and a PubSub message with a VolunteeringDeleted event
        event_data = {"eventType": "VolunteeringDeleted", "eventVersion": "1.0.0", "data": {"id": record_id}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}

        endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data"})

        # when posting to the push endpoint
        response = async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        assert response.status_code == 200
        content = json.loads(response.content)
        assert content["status"] == "OK"

        # then favorite was deleted
        assert not UserFavorite.objects.filter(
            user=user, favoritable_id=record_id, favoritable_type=favoritable_type
        ).exists()

        # and the ExternalVolunteeringOpportunity was also deleted
        assert not ExternalVolunteeringOpportunity.objects.filter(external_id=record_id).exists()
