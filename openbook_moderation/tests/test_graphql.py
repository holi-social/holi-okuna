import logging

import pytest
from asgiref.sync import async_to_sync
from benedict import benedict
from django.core.management import call_command
from django.test import AsyncClient

from comments.tests.helpers import get_post
from openbook.graphql_schema import schema
from openbook_auth.tests.helpers import get_user_with_id_data, get_user_with_id_raw
from openbook_common.tests.helpers import (
    make_community,
    make_fake_post_text,
    make_fake_post_title,
    make_user,
)
from openbook_moderation.enums import ContentType
from openbook_moderation.tests.helpers import approve_verify_moderated_object
from openbook_posts.tests.helpers import get_post_with_id_data, get_post_with_id_raw

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return AsyncClient()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestModeration:
    def test_report_post(self):
        posting_user = make_user()
        posting_user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)

        response = async_to_sync(schema.execute)(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=benedict({"request": {"user": reporting_user}}),
            variable_values=benedict(
                {
                    "objectId": str(post.id),
                    "contentType": ContentType.POST.value,
                    "description": "report",
                }
            ),
        )

        assert response.errors is None
        assert response.data["reportContent"]["success"] is True

        assert reporting_user.can_see_post(post) is True
        assert other_user.can_see_post(post) is True

        post_data = get_post_with_id_data(post, reporting_user)
        assert post_data["id"] == str(post.id)

        post_data = get_post_with_id_data(post, other_user)
        assert post_data["id"] == str(post.id)

        approve_verify_moderated_object(post.id, posting_user)

        response = get_post_with_id_raw(post.id, other_user)
        assert other_user.can_see_post(post) is False
        assert response.data["postById"] is None

    def test_report_post_comment(self):
        posting_user = make_user()
        posting_user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_post(text=post_text, title=post_title, is_public=True)
        comment = post.comment(text=f"comment text 1 @{posting_user.username}", commenter=posting_user)

        response = async_to_sync(schema.execute)(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=benedict({"request": {"user": reporting_user}}),
            variable_values=benedict(
                {
                    "objectId": str(comment.id),
                    "contentType": ContentType.POST_COMMENT.value,
                    "description": "report",
                }
            ),
        )

        assert response.errors is None
        assert response.data["reportContent"]["success"] is True

        post_data = get_post(post, reporting_user)
        assert len(post_data["comments"]) == 1

        approve_verify_moderated_object(comment.id, posting_user)

        post_data = get_post(post, other_user)
        assert len(post_data["comments"]) == 0

    @pytest.mark.skip("Fundamentally broken on Postgres, even though this test would work")
    def test_report_user(self):
        user = make_user()
        user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        user_before_report = get_user_with_id_data(user, reporting_user)
        assert user_before_report["id"] == user.username

        user_before_report = get_user_with_id_data(user)
        assert user_before_report["id"] == user.username

        response = async_to_sync(schema.execute)(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=benedict({"request": {"user": reporting_user}}),
            variable_values=benedict(
                {
                    "objectId": str(user.username),
                    "contentType": ContentType.USER.value,
                    "description": "report",
                }
            ),
        )

        assert response.errors is None
        assert response.data["reportContent"]["success"] is True

        response = get_user_with_id_raw(user, reporting_user)
        assert response.data is None

        user_before_approve = get_user_with_id_data(user, other_user)
        assert user_before_approve["id"] == user.username
        user_before_approve = get_user_with_id_data(user)
        assert user_before_approve["id"] == user.username

        approve_verify_moderated_object(user.id, user)

        response_after_approve = get_user_with_id_raw(user, other_user)
        assert response_after_approve.data["userById"] is None
        response_after_approve = get_user_with_id_raw(user)
        assert response_after_approve.data["userById"] is None

    def test_report_space(self):
        space_user = make_user()
        space_user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        space = make_community(creator=space_user)

        response = async_to_sync(schema.execute)(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=benedict({"request": {"user": reporting_user}}),
            variable_values=benedict(
                {
                    "objectId": str(space.id),
                    "contentType": ContentType.SPACE.value,
                    "description": "report",
                }
            ),
        )

        assert response.errors is None
        assert response.data["reportContent"]["success"] is True

        response = async_to_sync(schema.execute)(
            f"""
            query {{
                spaceById(idOrName: "{space.id}") {{
                    id
                }}
            }}
            """,
            context_value=benedict({"request": {"user": reporting_user}}),
        )
        assert response.errors is None
        assert len(response.data["spaceById"]) == 1
        assert response.data["spaceById"]["id"] == str(space.id)

        response = async_to_sync(schema.execute)(
            f"""
            query {{
                spaceById(idOrName: "{space.name}") {{
                    name
                }}
            }}
            """,
            context_value=benedict({"request": {"user": other_user}}),
        )
        assert response.errors is None
        assert len(response.data["spaceById"]) == 1
        assert response.data["spaceById"]["name"] == str(space.name)

        approve_verify_moderated_object(space.id, space_user)

        response = async_to_sync(schema.execute)(
            f"""
            query {{
                spaceById(idOrName: "{space.id}") {{
                    id
                }}
            }}
            """,
            context_value=benedict({"request": {"user": other_user}}),
        )
        assert response.data["spaceById"] is None
