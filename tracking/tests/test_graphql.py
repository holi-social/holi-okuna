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
class TestTracking(TestCase):
    def setUp(self):
        sys._called_from_test = True

    def tearDown(self):
        del sys._called_from_test

    @mock.patch("posthog.Posthog.capture")
    def test_no_tracking_without_analytics_consent(self, mock_posthog_capture):
        graphql_query = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
        """
        topic_ids = [str(make_topic().id) for _ in range(2)]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        valid_input = {"title": "valid", "description": "valid", "topics": topic_ids, "cover": valid_image}

        user = make_user(
            tracking_consent_analytics=False,
            tracking_consent_personalization=True,
        )
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )
        assert response.errors is None
        mock_posthog_capture.assert_not_called()

    # TODO test that we only track on trackingConsentAnalytics
    # TODO test we don't track if only trackingConsentPersonalization is given
    # TODO test that user ID is correct

    # TODO maybe use https://pypi.org/project/django-lifecycle/0.5.0/ instead

    @mock.patch("posthog.Posthog.capture")
    def test_emits_tracking_event_create_space(self, mock_posthog_capture):
        graphql_query = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
        """
        topic_ids = [str(make_topic().id) for _ in range(2)]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        valid_input = {"title": "valid", "description": "valid", "topics": topic_ids, "cover": valid_image}

        user = make_user(
            tracking_consent_analytics=True,
            tracking_consent_personalization=True,
        )
        response = async_to_sync(schema.execute)(
            graphql_query,
            context_value=benedict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None
        mock_posthog_capture.assert_any_call(
            distinct_id=user.username,
            event="space_created",
            properties=standard_properties,
        )
