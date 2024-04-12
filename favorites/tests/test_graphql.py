import logging

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import AsyncClient

from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    make_user,
    simple_jpeg_bytes,
)
from openbook_common.utils.model_loaders import get_insight_model
from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


# This tests a deprecated way of bookmarking insights, that uses the openbook_auth package bookmark endpoints
# keep for versions <= 1.14.5,


def bookmark_insight(user, insight_id):
    return async_to_sync(schema.execute)(
        f"""
        mutation {{
            bookmarkInsight(insightId: "{insight_id}") {{
                success
            }}
        }}
        """,
        context_value=benedict({"request": {"user": user}}),
    )


def remove_insight_bookmark(user, insight_id):
    return async_to_sync(schema.execute)(
        f"""
        mutation {{
            removeInsightBookmark(insightId: "{insight_id}") {{
                success
            }}
        }}
        """,
        context_value=benedict({"request": {"user": user}}),
    )


@pytest.mark.django_db
class TestUsers:
    def test_cannot_bookmark_insight_if_anonymous(self):
        insight_author = make_user()
        insight_model = get_insight_model()
        insight = insight_model.objects.create(
            creator=insight_author,
            title="insight_model",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=timezone.now(),
        )

        response = bookmark_insight(AnonymousUser, insight_id=insight.id)

        assert_is_unauthorized(response)

    def test_cannot_remove_insight_bookmark_if_anonymous(self):
        insight_author = make_user()
        insight_model = get_insight_model()
        insight = insight_model.objects.create(
            creator=insight_author,
            title="Insight",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=timezone.now(),
        )

        response = remove_insight_bookmark(AnonymousUser, insight_id=insight.id)

        assert_is_unauthorized(response)

    def test_can_bookmark_insight_if_authenticated(self):
        user = make_user()
        insight_author = make_user()
        insight_model = get_insight_model()
        insight = insight_model.objects.create(
            creator=insight_author,
            title="Insight",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=timezone.now(),
        )

        response = bookmark_insight(user, insight_id=insight.id)

        assert response.data["bookmarkInsight"]["success"]
        assert user.profile.favorite_insights.count() == 1

    def test_can_remove_insight_bookmark_if_authenticated(self):
        user = make_user()
        insight_author = make_user()
        insight_model = get_insight_model()
        insight = insight_model.objects.create(
            creator=insight_author,
            title="Insight",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=timezone.now(),
        )

        bookmark_insight(user, insight_id=insight.id)
        assert user.profile.favorite_insights.count() == 1

        response = remove_insight_bookmark(user, insight_id=insight.id)

        assert response.data["removeInsightBookmark"]["success"]
        assert user.profile.favorite_insights.count() == 0
