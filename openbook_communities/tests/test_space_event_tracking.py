import logging
from unittest import mock

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from openbook.graphql_schema import schema
from openbook_common.tracking import initialize_tracking, PostHogConfig
from openbook_common.tests.helpers import (
    make_user,
    make_topic,
    make_community,
    make_skill,
    make_community_task,
    simple_jpeg_bytes,
)


logger = logging.getLogger(__name__)

standard_properties = {
    "trackingConsentAnalytics": True,
    "trackingConsentPersonalization": True,
    "event_version__major": 1,
    "event_version__minor": 0,
    "event_version__patch": 0,
}


@pytest.mark.django_db
class TestSpaceEvents(TestCase):
    def setUp(self):
        initialize_tracking(PostHogConfig(api_key="fake_api_key", host="fake_host", disable_for_testing=True))

    @staticmethod
    def __input_create_task(space, skill):
        return {
            "spaceId": str(space.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

    @mock.patch("posthog.Posthog.capture")
    def test_tracks_space_created(self, mock_posthog_capture):
        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
        input_create_space = {
            "title": "valid",
            "description": "valid",
            "topics": [str(make_topic().id) for _ in range(2)],
            "cover": (SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)),
        }
        mock_posthog_capture.reset_mock()

        graphql_query = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": input_create_space},
        )

        assert response.errors is None
        space_id = response.data["createSpace"]["id"]

        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="spaceCreated",
            properties={**standard_properties, "spaceId": space_id},
        )

    @mock.patch("posthog.Posthog.capture")
    def test_tracks_space_updated(self, mock_posthog_capture):
        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
        space = make_community(creator=user)
        mock_posthog_capture.reset_mock()

        graphql_query = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    onboarding { steps { text } }
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": {"id": str(space.id), "title": "New Space Title"}},
        )

        assert response.errors is None
        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="spaceUpdated",
            properties={**standard_properties, "spaceId": str(space.id)},
        )

    @mock.patch("posthog.Posthog.capture")
    def test_tracks_space_deleted(self, mock_posthog_capture):
        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
        space = make_community(creator=user)
        mock_posthog_capture.reset_mock()

        graphql_query = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(space.id)},
        )

        assert response.errors is None
        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="spaceDeleted",
            properties={**standard_properties, "spaceId": str(space.id)},
        )

    @mock.patch("posthog.Posthog.capture")
    def test_tracks_space_task_created(self, mock_posthog_capture):
        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
        space = make_community(creator=user)
        skill = make_skill()
        mock_posthog_capture.reset_mock()

        graphql_query = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                }
            }
        """
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": (self.__input_create_task(space, skill))},
        )

        assert response.errors is None
        task_id = response.data["createTask"]["id"]

        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="taskCreated",
            properties={**standard_properties, "spaceId": str(space.id), "taskId": str(task_id)},
        )

    @mock.patch("posthog.Posthog.capture")
    def test_tracks_space_task_updated(self, mock_posthog_capture):
        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
        space = make_community(creator=user)
        skill = make_skill()
        task = make_community_task(space)
        mock_posthog_capture.reset_mock()

        graphql_query = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                }
            }
        """

        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={
                "input": {
                    **(self.__input_create_task(space, skill)),
                    "taskId": str(task.id),
                }
            },
        )

        assert response.errors is None

        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="taskUpdated",
            properties={**standard_properties, "spaceId": str(space.id), "taskId": str(task.id)},
        )

    @mock.patch("posthog.Posthog.capture")
    def test_tracks_space_task_deleted(self, mock_posthog_capture):
        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
        space = make_community(creator=user)
        task = make_community_task(space)
        mock_posthog_capture.reset_mock()

        graphql_query = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
        """

        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.errors is None

        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="taskDeleted",
            properties={**standard_properties, "spaceId": str(space.id), "taskId": str(task.id)},
        )
