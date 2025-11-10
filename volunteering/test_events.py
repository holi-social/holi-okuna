import json
import pytest
import base64

from django.test import AsyncClient, TransactionTestCase
from django.urls import reverse
from asgiref.sync import async_to_sync

from volunteering.models import VolunteeringOpportunityStatus, Status
from openbook_common.tests.helpers import make_user


@pytest.mark.django_db
class PubSubPushEndpointVolunteeringStatusesSyncingTestCase(TransactionTestCase):
    def test_integration_with_volunteering_opportunity_status_model(self):
        # given a volunteering for the external volunteering opportunity
        client = AsyncClient()
        user = make_user()
        some_external_vo_id = "1928319283"

        VolunteeringOpportunityStatus.objects.create(
            user=user,
            external_volunteering_opportunity_id=some_external_vo_id,
            status=Status.CONTACTED,
        )

        # then our volunteering exists
        assert VolunteeringOpportunityStatus.objects.filter(
            user=user, external_volunteering_opportunity_id=some_external_vo_id
        ).exists()

        # when notifying okuna about the deletion of the external volunteering opportunity
        event_data = {"eventType": "VolunteeringDeleted", "eventVersion": "1.0.0", "data": {"id": some_external_vo_id}}
        encoded_data = base64.b64encode(json.dumps(event_data).encode("utf-8")).decode("utf-8")
        payload = {"message": {"data": encoded_data}}
        endpoint = reverse("pubsub_push", kwargs={"topic_name": "external-data"})
        async_to_sync(client.post)(endpoint, payload, content_type="application/json")

        # then our volunteering is deleted
        assert not VolunteeringOpportunityStatus.objects.filter(
            user=user, external_volunteering_opportunity_id=some_external_vo_id
        ).exists()
