import json
import pytest
import base64

from benedict import benedict
from django.test import AsyncClient, TransactionTestCase
from django.urls import reverse
from asgiref.sync import async_to_sync

from openbook.graphql_schema import schema
from openbook_common.enums import VisibilityType
from volunteering.models import VolunteeringOpportunityStatus, Status
from openbook_common.tests.helpers import make_user, make_community, make_community_task


@pytest.mark.django_db
class PubSubPushEndpointVolunteeringStatusesSyncingTestCase(TransactionTestCase):
    def test_deletion_of_evo_in_typesesense_deletes_volunteering_status(self):
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

    def test_deleting_of_task_deletes_volunteering_status(self):
        # given a volunteering for a task
        user = make_user()
        community = make_community()
        task = make_community_task(community)

        VolunteeringOpportunityStatus.objects.create(
            user=user,
            external_volunteering_opportunity_id=task.id,
            status=Status.CONTACTED,
        )

        # then our volunteering exists
        assert VolunteeringOpportunityStatus.objects.filter(
            user=user, external_volunteering_opportunity_id=task.id
        ).exists()

        # when deleting the task
        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        async_to_sync(schema.execute)(
            delete_task_mutation,
            variable_values={"id": str(task.id)},
            context_value=benedict({"request": {"user": community.creator}}),
        )

        # then our volunteering is deleted
        assert not VolunteeringOpportunityStatus.objects.filter(
            user=user, external_volunteering_opportunity_id=task.id
        ).exists()

    def test_depublishing_of_task_deletes_volunteering_status(self):
        # given a volunteering for a public task
        user = make_user()
        community = make_community()
        task = make_community_task(community, visibility=VisibilityType.PUBLIC)

        VolunteeringOpportunityStatus.objects.create(
            user=user,
            external_volunteering_opportunity_id=task.id,
            status=Status.CONTACTED,
        )

        # then our volunteering exists
        assert VolunteeringOpportunityStatus.objects.filter(
            user=user, external_volunteering_opportunity_id=task.id
        ).exists()

        # when making the task private
        update_task_mutation = """
                  mutation test($input: UpdateTaskInput!) {
                      updateTask(input: $input) {
                          id
                      }
                  }
                  """

        task_update = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
            "duration": "INDETERMINATE",
            "interactionType": "CHAT",
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = async_to_sync(schema.execute)(
            update_task_mutation,
            context_value=benedict({"request": {"user": community.creator}}),
            variable_values={"input": task_update},
        )

        assert response.errors is None

        # then our volunteering is deleted
        assert not VolunteeringOpportunityStatus.objects.filter(
            user=user, external_volunteering_opportunity_id=task.id
        ).exists()
