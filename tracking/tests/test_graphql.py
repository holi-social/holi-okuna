import sys
import logging
from unittest import mock

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from openbook.graphql_schema import schema
from openbook_common.tests.helpers import (
    make_user,
    make_topic,
    make_community,
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


# TODO maybe use https://pypi.org/project/django-lifecycle/0.5.0/ instead


@pytest.mark.django_db
class TestTracking(TestCase):
    def setUp(self):
        sys._called_from_test = True

    def tearDown(self):
        del sys._called_from_test

    @staticmethod
    def __input_create_space():
        topic_ids = [str(make_topic().id) for _ in range(2)]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        return {"title": "valid", "description": "valid", "topics": topic_ids, "cover": valid_image}

    @mock.patch("posthog.Posthog.capture")
    def test_no_tracking_without_analytics_consent(self, mock_posthog_capture):
        graphql_query = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
        """
        user = make_user(
            tracking_consent_analytics=False,
            tracking_consent_personalization=True,
        )
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": self.__input_create_space()},
        )
        assert response.errors is None
        mock_posthog_capture.assert_not_called()

    @mock.patch("posthog.Posthog.capture")
    def test_emits_tracking_event_space_created(self, mock_posthog_capture):
        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
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
            variable_values={"input": self.__input_create_space()},
        )

        assert response.errors is None
        space_id = response.data["createSpace"]["id"]

        mock_posthog_capture.assert_called_once_with(
            distinct_id=user.username,
            event="space_created",
            properties={**standard_properties, "id": space_id},
        )

    @mock.patch("posthog.Posthog.capture")
    def test_emits_tracking_event_space_updated(self, mock_posthog_capture):
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
            event="space_updated",
            properties={**standard_properties, "id": str(space.id)},
        )

    @mock.patch("posthog.Posthog.capture")
    def test_emits_tracking_event_space_deleted(self, mock_posthog_capture):
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
            event="space_deleted",
            properties={**standard_properties, "id": str(space.id)},
        )
