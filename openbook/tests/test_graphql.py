import copy
import json
import logging
import pytest
from django.test import Client
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from unittest import mock

from django.conf import settings
from benedict import BeneDict
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis import geos
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from requests.models import Response
from rest_framework import status

from openbook.graphql_schema import (
    ContentType,
    SpaceUserConnectionType,
    UpdateConnectionAction,
    schema,
)
from openbook.graphql_types import VisibilityFilter
from openbook_auth.models import User, UserConnectionStatus, EngagementLevelChoice
from openbook_common.models import AppVersion
from openbook_common.tests.helpers import (
    get_test_images,
    get_test_videos,
    make_authentication_headers_for_user,
    make_collaboration_tool,
    make_community,
    make_community_task,
    make_external_link,
    make_fake_post_text,
    make_fake_post_title,
    make_sdg,
    make_skill,
    make_topic,
    make_user,
    simple_jpeg_bytes,
)
from openbook_common.utils.model_loaders import (
    get_community_admin_privileges_granted_notification_model,
    get_community_admin_privileges_revoked_notification_model,
    get_community_membership_revoked_notification_model,
)
from openbook_communities.models import Community, CommunityNotificationsSubscription, CommunityMembership
from openbook_common.types import VisibilityType, NeedUpdateType
from openbook_insights.models import Insight
from openbook_moderation.models import ModeratedObject
from django.core.management import call_command
from openbook.tests.test_data import geolocation, geolocation_id, geolocation_geometry
from openbook_notifications.models import CommunityNewPostNotification
from openbook_posts.models import PostCommentReaction, PostUserMention, PostComment, PostImage, Post

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def client():
    return Client()


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "openbook_circles/fixtures/circles.json")
        call_command("loaddata", "openbook_moderation/fixtures/moderation_categories.json")


@pytest.mark.django_db
class TestUsers:
    def test_get_authenticated_user_returns_self_reference(self, client):
        user = make_user()
        headers = make_authentication_headers_for_user(user)

        endpoint = reverse("graphql-endpoint")
        graphql_query = """
            query {
                authenticatedUser {
                    id
                    fullName
                    engagementLevel
                }
            }
        """
        response = client.post(
            path=endpoint,
            data=json.dumps({"query": graphql_query}),
            content_type="application/json",
            **headers,
        )

        assert response.status_code == status.HTTP_200_OK

        authenticated_user = json.loads(response.content)["data"]["authenticatedUser"]
        assert authenticated_user["id"] == str(user.uuid)
        assert authenticated_user["fullName"] == user.profile.full_name()
        assert authenticated_user["engagementLevel"] == user.profile.engagement_level

    def test_get_user_by_name_returns_only_matching_users_without_logged_in_user(self):
        expected_users = [
            make_user(name="Peter", last_name="Muster"),
            make_user(name="Peter", last_name="Mudtke"),
        ]
        make_user(name="Fritz", last_name="Meier")
        user = make_user(name="Peter", last_name="Moser")

        executed = schema.execute_sync(
            """
            query {
                userByName(substring: "er M") {
                    totalResults
                    data {
                        firstName
                        lastName
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
        )
        self.assert_paged_results_equal(
            results=executed.data["userByName"],
            expected_data=[{"firstName": u.name, "lastName": u.last_name} for u in expected_users],
        )

    def test_get_user_by_name_first_name_matches_first(self):
        make_user(name="Thomas", last_name="Petersen")
        make_user(name="Peter", last_name="Muster")
        make_user(name="Petra", last_name="Meier")
        make_user(name="Fritz", last_name="Meier")

        executed = schema.execute_sync(
            """
            query {
                userByName(substring: "Pet") {
                    totalResults
                    data {
                        firstName
                        lastName
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )
        assert executed.data["userByName"]["totalResults"] == 3
        assert executed.data["userByName"]["data"][0]["firstName"] == "Peter"
        assert executed.data["userByName"]["data"][1]["firstName"] == "Petra"
        assert executed.data["userByName"]["data"][2]["firstName"] == "Thomas"

    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("openbook.graphql_schema.publish_user_name_updated_event")
    def test_can_update_authenticated_user(self, mock_publish_user_name_updated_event, mock_patch):
        response = Response()
        response.status_code = 200
        response._content = str.encode(json.dumps({}))
        mock_patch.return_value = response
        user = make_user(name="Fritz", last_name="Meier")
        community = make_community()
        community.add_member(user)
        pronouns = "She/her"
        location = "Bremerhaven"

        assert User.objects.get(username=user.username).profile.pronouns != pronouns
        first_name = "Peter"
        last_name = "Shaw"
        engagement_level = EngagementLevelChoice.INITIATOR

        json_body = [
            {"op": "add", "path": "/traits/given_name", "value": f"{first_name}"},
            {"op": "add", "path": "/traits/family_name", "value": f"{last_name}"},
            {"op": "add", "path": "/traits/name", "value": f"{first_name} {last_name}"},
        ]

        executed = schema.execute_sync(
            """
            mutation test($input: UpdateAuthenticatedUserInput!) {
                updateAuthenticatedUser(input: $input) {
                    id
                    pronouns
                    location
                    geolocation {
                      latitude
                      longitude
                    }
                    geolocationId
                    engagementLevel
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={
                "input": {
                    "pronouns": pronouns,
                    "firstName": first_name,
                    "lastName": last_name,
                    "location": location,
                    "geolocation": geolocation,
                    "engagementLevel": engagement_level,
                }
            },
        )
        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
        )
        updated_user = executed.data["updateAuthenticatedUser"]
        graphql_pronouns = updated_user["pronouns"]
        persisted_profile = User.objects.get(username=user.username).profile

        assert graphql_pronouns == persisted_profile.pronouns
        assert graphql_pronouns == pronouns
        assert last_name == persisted_profile.last_name
        assert first_name == persisted_profile.name
        assert persisted_profile.engagement_level == EngagementLevelChoice.INITIATOR
        assert location == persisted_profile.location
        assert geolocation_id == persisted_profile.geolocation_id
        # TODO: Only for temporary backwards compatibility, adjust in HOLI-4353
        assert updated_user["geolocation"] is None
        assert persisted_profile.geolocation is not None
        assert geos.GEOSGeometry(json.dumps(geolocation_geometry)) == persisted_profile.geolocation

        mock_publish_user_name_updated_event.assert_called_once_with(user=user)

    @mock.patch("openbook_auth.tasks.requests.delete")
    @mock.patch("openbook.graphql_schema.publish_user_deleted_event")
    @mock.patch("openbook.graphql_schema.publish_space_deleted_event")
    def test_can_delete_authenticated_user(
        self, mock_publish_space_deleted_event, mock_publish_user_deleted_event, mock_delete
    ):
        response = Response()
        response.status_code = 204
        response._content = str.encode(json.dumps({}))
        mock_delete.return_value = response

        user = make_user(name="Fritz", last_name="Meier")
        space = make_community(creator=user)

        mutation_response = schema.execute_sync(
            """
            mutation test {
                deleteAuthenticatedUser {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
        )
        mock_delete.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
        )

        assert mutation_response.data["deleteAuthenticatedUser"]["success"] is True

        mock_publish_user_deleted_event.assert_called_once_with(user=user)
        mock_publish_space_deleted_event.assert_called_once_with(space)

    @mock.patch("openbook_auth.tasks.requests.delete")
    @mock.patch("openbook.graphql_schema.publish_user_deleted_event")
    @mock.patch("openbook.graphql_schema.publish_space_deleted_event")
    def test_cannot_delete_space_if_deleted_authenticated_user_not_only_admin(
        self, mock_publish_space_deleted_event, mock_publish_user_deleted_event, mock_delete
    ):
        response = Response()
        response.status_code = 204
        response._content = str.encode(json.dumps({}))
        mock_delete.return_value = response

        user = make_user(name="Fritz", last_name="Meier")
        space = make_community(creator=user)

        admin = make_user(name="John", last_name="Doe")
        space.add_member(admin)
        space.add_administrator(admin)

        mutation_response = schema.execute_sync(
            """
            mutation test {
                deleteAuthenticatedUser {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
        )
        mock_delete.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
        )

        assert mutation_response.data["deleteAuthenticatedUser"]["success"] is True

        mock_publish_user_deleted_event.assert_called_once_with(user=user)
        mock_publish_space_deleted_event.assert_not_called()

    def test_can_perform_connection_workflow(self):
        first_user = make_user(name="Fritz", last_name="Meier")
        second_user = make_user(name="Gesine", last_name="Schinder")

        assert first_user.is_connected_with_user(second_user) is False

        connection_request_response = self.connect_to_user(first_user, second_user)

        assert connection_request_response.data["updateConnectionWithUser"]["id"] == second_user.username

        assert second_user.is_pending_confirm_connection_for_user_with_id(first_user.pk) is True
        assert first_user.get_connection_status_with_user_id(second_user.pk) == UserConnectionStatus.REQUESTED

        connection_confirm_response = self.connect_to_user(second_user, first_user)

        assert connection_confirm_response.data["updateConnectionWithUser"]["id"] == first_user.username

        assert first_user.is_fully_connected_with_user_with_id(second_user.pk) is True
        assert second_user.is_fully_connected_with_user_with_id(first_user.pk) is True

    def test_can_fetch_post(self):
        posting_user = make_user()
        mentioned_user = make_user(name="Mentioned")
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        post.comment(text=f"comment text 1 @{posting_user.username}", commenter=other_user)
        post.comment(
            text=f"comment text 2 @{mentioned_user.username} @{posting_user.username}",
            commenter=other_user,
        )
        post.comment(
            text=f"comment text 3 @{mentioned_user.username} @{posting_user.username}",
            commenter=other_user,
        )

        post_data = self.get_post_with_id_data(post)

        assert post_data["text"] == post_text
        assert post_data["title"] == post_title
        assert post_data["image"] is None
        assert post_data["creator"]["id"] == str(posting_user.uuid)
        assert post_data["created"] is not None
        assert post_data["numberOfComments"] == 3
        assert post_data["involvedUsers"]["totalResults"] == 2
        assert len(post_data["comments"]) == 3
        assert post_data["comments"][0]["text"] == f"comment text 1 @{posting_user.username}"
        assert post_data["commenters"]["totalResults"] == 1
        assert post_data["commenters"]["data"][0]["firstName"] == other_user.name

    def test_can_fetch_post_with_image(self):
        posting_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()
        image_name = "foo.jpg"

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
            image=SimpleUploadedFile(name=image_name, content=simple_jpeg_bytes),
        )

        post_data = self.get_post_with_id_data(post)

        assert post_data["text"] == post_text
        assert post_data["title"] == post_title
        assert image_name in post_data["image"]["url"]
        assert post_data["image"]["width"] == 1
        assert post_data["image"]["height"] == 1
        assert post_data["creator"]["id"] == str(posting_user.uuid)
        assert post_data["created"] is not None

    def test_cant_fetch_post_draft(self):
        posting_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(text=post_text, title=post_title, is_draft=True)

        response = self.get_post_with_id_raw(post)

        post_data = response.data["postById"]
        assert post_data is None
        assert "Post not found" in response.errors[0].message

    def test_can_delete_post_comment(self):
        posting_user = make_user()
        comment_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text=f"comment text 2", commenter=comment_user)

        assert post.comments.count() == 2
        response = self.delete_post_comment(comment.id, comment_user)
        assert response.errors is None
        assert response.data["deletePostComment"]["success"] == True
        assert post.comments.count() == 1
        assert comment.id not in post.comments.values_list("id", flat=True)
        assert reaction.id not in PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_cant_delete_post_comment_of_other_user(self):
        posting_user = make_user()
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text=f"comment text 2", commenter=comment_user)

        assert post.comments.count() == 2
        response = self.delete_post_comment(comment.id, other_user)
        assert response.data is None

        assert post.comments.count() == 2
        assert comment.id in post.comments.values_list("id", flat=True)
        assert reaction.id in PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_cant_delete_post_comment_not_exist(self):
        posting_user = make_user()
        comment_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text", commenter=comment_user)
        reaction = comment.react(posting_user, "HEART")
        post.comment(text=f"comment text 2", commenter=comment_user)

        assert post.comments.count() == 2
        response = self.delete_post_comment("00000000-0000-0000-0000-000000000000", comment_user)
        assert response.data is None

        assert post.comments.count() == 2
        assert comment.id in post.comments.values_list("id", flat=True)
        assert reaction.id in PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)

    def test_react_to_post(self):
        posting_user = make_user()
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )

        self.react_to_post(post, "SET", posting_user)
        executed = self.react_to_post(post, "SET", posting_user)  # setting twice is same as setting once
        updated_post = executed.data["updatePostReaction"]

        assert updated_post["myReaction"]["HEART"] == 1
        assert updated_post["reactions"]["HEART"] == 1

        post_data = self.get_post_with_id_data(post, other_user)
        assert post_data["myReaction"]["HEART"] == 0
        assert post_data["reactions"]["HEART"] == 1

        self.react_to_post(post, "REMOVE", posting_user)
        executed = self.react_to_post(post, "REMOVE", posting_user)  # setting twice is same as setting once
        updated_post = executed.data["updatePostReaction"]
        assert updated_post["myReaction"]["HEART"] == 0
        assert updated_post["reactions"]["HEART"] == 0

    def test_react_to_post_comment(self):
        posting_user = make_user()
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text", commenter=other_user)

        self.react_to_post_comment(comment, "SET", posting_user)
        executed = self.react_to_post_comment(comment, "SET", posting_user)  # setting twice is same as setting once
        updated_post_comment = executed.data["updatePostCommentReaction"]

        assert updated_post_comment["myReaction"]["HEART"] == 1
        assert updated_post_comment["reactions"]["HEART"] == 1

        post_data = self.get_post_with_id_data(post, other_user)
        assert post_data["myReaction"]["HEART"] == 0
        assert post_data["reactions"]["HEART"] == 0
        assert post_data["comments"][0]["myReaction"]["HEART"] == 0
        assert post_data["comments"][0]["reactions"]["HEART"] == 1

        self.react_to_post_comment(comment, "REMOVE", posting_user)
        executed = self.react_to_post_comment(comment, "REMOVE", posting_user)  # setting twice is same as setting once
        updated_post_comment = executed.data["updatePostCommentReaction"]
        assert updated_post_comment["myReaction"]["HEART"] == 0
        assert updated_post_comment["reactions"]["HEART"] == 0

    def react_to_post(self, post, action, posting_user):
        return schema.execute_sync(
            """
            mutation test($id: UUID!, $reactionType: ReactionType!, $reactionAction: ReactionAction!) {
                updatePostReaction(id: $id, reactionType: $reactionType, reactionAction: $reactionAction) {
                    myReaction {
                        HEART
                    }
                    reactions {
                        HEART
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": posting_user}}),
            variable_values={
                "id": str(post.id),
                "reactionType": "HEART",
                "reactionAction": action,
            },
        )

    def react_to_post_comment(self, post_comment, action, posting_user):
        return schema.execute_sync(
            """
            mutation test($id: UUID!, $reactionType: ReactionType!, $reactionAction: ReactionAction!) {
                updatePostCommentReaction(id: $id, reactionType: $reactionType, reactionAction: $reactionAction) {
                    myReaction {
                        HEART
                    }
                    reactions {
                        HEART
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": posting_user}}),
            variable_values={
                "id": str(post_comment.id),
                "reactionType": "HEART",
                "reactionAction": action,
            },
        )

    def delete_post_comment(self, post_comment_id, user):
        return schema.execute_sync(
            """
            mutation test($id: UUID!) {
                deletePostComment(id: $id) {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={
                "id": str(post_comment_id),
            },
        )

    def create_space_post(self, user, info):
        return schema.execute_sync(
            """
            mutation test($input: CreatePostInput!){
                createSpacePost(input: $input) {
                    id
                    title
                    posts {
                        totalResults
                        data {
                            title
                            text
                            isPublic
                            created
                        }
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": info},
        )

    def create_space_post_2(self, user, info):
        return schema.execute_sync(
            """
            mutation test($input: CreatePostInput!){
                createSpacePost2(input: $input) {
                    id
                    title
                    space {
                      id
                      posts {
                        totalResults
                      }
                    }
                    text
                    isPublic
                    created
                    
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": info},
        )

    def update_space_post(self, user, info):
        return schema.execute_sync(
            """
            mutation test($input: UpdatePostInput!){
                updateSpacePost(input: $input) {
                    id
                    title
                    space {
                      id
                      posts {
                        totalResults
                      }
                    }
                    text
                    isPublic
                    created
                    image {
                        url
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": info},
        )

    def test_space_user_can_create_space_post(self):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)

        # space admin can create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(space_admin, input_data)

        data = response.data["createSpacePost"]
        posts_data = data["posts"]["data"]

        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == 1
        assert posts_data[0]["text"] == input_data["text"]
        assert posts_data[0]["isPublic"] is True

        # space admin can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(space_admin, input_data)

        data = response.data["createSpacePost"]
        posts_data = data["posts"]["data"]

        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == 2
        assert posts_data[0]["text"] == input_data["text"]
        assert posts_data[0]["isPublic"] is False

    def test_member_user_can_create_only_member_visibility_space_post(self):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)

        # member user can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(member_user, input_data)

        data = response.data["createSpacePost"]
        posts_data = data["posts"]["data"]

        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == 1
        assert posts_data[0]["text"] == input_data["text"]
        assert posts_data[0]["isPublic"] is False

        # member user cannot create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(member_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert (
            "You cannot add a public post to a community you're not administrator of"
            in response.errors[0].extensions["errors"]
        )

    def test_cant_create_space_post_external_user(self):
        space_admin = make_user()
        external_user = make_user()
        space = make_community(creator=space_admin)

        # not member user can't create post for the space
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(external_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert "You cannot post to a community you're not member of" in response.errors[0].extensions["errors"]

    def test_cant_create_space_post_invalid_input(self):
        space_admin = make_user()
        space = make_community(creator=space_admin)

        # test space id field is missing
        input_data = {
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'spaceId' of required type 'UUID!' was not provided" in response.errors[0].message

        # test post text field is missing
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
        }

        response = self.create_space_post(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'text' of required type 'String!' was not provided" in response.errors[0].message

        # test visibility field is missing
        input_data = {"spaceId": str(space.id), "text": make_fake_post_text()}

        response = self.create_space_post(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'visibility' of required type 'VisibilityType!' was not provided" in response.errors[0].message

    def test_space_user_can_create_space_post_2(self):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)

        # space admin can create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post_2(space_admin, input_data)

        data = response.data["createSpacePost2"]

        assert data["space"]["id"] == str(space.id)
        assert data["space"]["posts"]["totalResults"] == 1
        assert data["text"] == input_data["text"]
        assert data["isPublic"] is True

        # space admin can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post_2(space_admin, input_data)

        data = response.data["createSpacePost2"]

        assert data["space"]["id"] == str(space.id)
        assert data["space"]["posts"]["totalResults"] == 2
        assert data["text"] == input_data["text"]
        assert data["isPublic"] is False

    def test_member_user_can_create_only_member_visibility_space_post_2(self):
        space_admin = make_user()
        member_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(member_user)

        # member user can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post_2(member_user, input_data)

        data = response.data["createSpacePost2"]

        assert data["space"]["id"] == str(space.id)
        assert data["space"]["posts"]["totalResults"] == 1
        assert data["text"] == input_data["text"]
        assert data["isPublic"] == False

        # member user cannot create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post_2(member_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert (
            "You cannot add a public post to a community you're not administrator of"
            in response.errors[0].extensions["errors"]
        )

    def test_cant_create_space_post_external_user_2(self):
        space_admin = make_user()
        external_user = make_user()
        space = make_community(creator=space_admin)

        # not member user can't create post for the space
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post_2(external_user, input_data)

        assert response.errors is not None
        assert response.data is None
        assert "You cannot post to a community you're not member of" in response.errors[0].extensions["errors"]

    def test_cant_create_space_post_invalid_input_2(self):
        space_admin = make_user()
        space = make_community(creator=space_admin)

        # test space id field is missing
        input_data = {
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post_2(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'spaceId' of required type 'UUID!' was not provided" in response.errors[0].message

        # test post text field is missing
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
        }

        response = self.create_space_post_2(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'text' of required type 'String!' was not provided" in response.errors[0].message

        # test visibility field is missing
        input_data = {"spaceId": str(space.id), "text": make_fake_post_text()}

        response = self.create_space_post_2(space_admin, input_data)
        assert response.errors is not None
        assert response.data is None
        assert "Field 'visibility' of required type 'VisibilityType!' was not provided" in response.errors[0].message

    def test_space_user_can_edit_space_post(self):
        space_admin = make_user()
        posting_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(posting_user)
        space.add_administrator(posting_user)

        space_post = Post.create_post(
            creator=posting_user,
            community_id=space.id,
            image=SimpleUploadedFile(name="foo.jpg", content=simple_jpeg_bytes),
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            circles_ids=[],
        )

        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        # test post update with replace of the post image
        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
            "title": None,
            "image": valid_image,
        }

        response = self.update_space_post(posting_user, input_data)
        assert response.errors is None
        assert response.data is not None

        data = response.data["updateSpacePost"]
        assert data["id"] == str(space_post.id)
        assert data["space"]["posts"]["totalResults"] == 1
        assert data["title"] is None
        assert data["text"] == input_data["text"]
        assert data["isPublic"] is True
        assert "/cover.jpg/" in data["image"]["url"]

        # test post update with removal of the post image
        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
            "title": None,
            "image": None,
        }

        response = self.update_space_post(posting_user, input_data)
        assert response.errors is None
        assert response.data is not None

        data = response.data["updateSpacePost"]
        assert data["id"] == str(space_post.id)
        assert data["space"]["posts"]["totalResults"] == 1
        assert data["title"] is None
        assert data["text"] == input_data["text"]
        assert data["isPublic"] is True
        assert data["image"] is None

    def test_cant_edit_space_post_to_public_visibility_member_user(self):
        space_admin = make_user()
        posting_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(posting_user)

        post_title = make_fake_post_title()
        post_text = make_fake_post_text()
        space_post = Post.create_post(
            creator=posting_user,
            community_id=space.id,
            image=SimpleUploadedFile(name="foo.jpg", content=simple_jpeg_bytes),
            text=post_text,
            title=post_title,
            circles_ids=[],
        )

        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
            "title": make_fake_post_title(),
        }

        response = self.update_space_post(posting_user, input_data)
        assert response.errors is not None
        assert response.data is None
        assert (
            "You cannot add a public post to a community you're not administrator of"
            in response.errors[0].extensions["errors"]
        )

        space_post.refresh_from_db()
        assert space_post.title == post_title
        assert "/foo.jpg/" in space_post.image.image.url

    def test_cant_edit_space_post_other_user(self):
        space_admin = make_user()
        posting_user = make_user()
        other_user = make_user()
        space = make_community(creator=space_admin)
        space.add_member(posting_user)
        space.add_member(other_user)

        post_title = make_fake_post_title()
        post_text = make_fake_post_text()
        space_post = Post.create_post(
            creator=posting_user,
            community_id=space.id,
            image=SimpleUploadedFile(name="foo.jpg", content=simple_jpeg_bytes),
            text=post_text,
            title=post_title,
            circles_ids=[],
        )

        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        input_data = {
            "postId": str(space_post.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
            "title": None,
            "image": valid_image,
        }

        response = self.update_space_post(other_user, input_data)
        assert response.errors is not None
        assert response.data is None
        assert response.errors[0].message == "This post does not belong to you."

        space_post.refresh_from_db()
        assert space_post.title == post_title
        assert "/foo.jpg/" in space_post.image.image.url

    def test_can_delete_space_post(self):
        space_admin = make_user()
        posting_user = make_user()
        subscriber_user = make_user()
        image_name = "test-image.jpg"

        space = make_community(creator=space_admin)
        space.add_member(posting_user)
        space.add_member(subscriber_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=subscriber_user
        )

        post = posting_user.create_community_encircled_post(
            space.id,
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            image=SimpleUploadedFile(name=image_name, content=simple_jpeg_bytes),
            visibility=VisibilityType.MEMBERS.value,
        )
        PostUserMention.create_post_user_mention(user=space_admin, post=post)
        PostComment.create_comment(text=make_fake_post_text(), post=post, commenter=posting_user)

        response = self.delete_space_post(post.id, posting_user)

        assert response.errors is None
        assert response.data["deleteSpacePost"]["posts"]["totalResults"] == 0

        assert CommunityNewPostNotification.objects.filter(post=post).count() == 0
        assert PostUserMention.objects.filter(post=post).count() == 0
        assert PostComment.objects.filter(post=post).count() == 0
        assert PostImage.objects.filter(post=post).count() == 0

    def test_can_not_delete_space_post(self):
        space_admin = make_user()
        posting_user = make_user()
        image_name = "test-image.jpg"

        space = make_community(creator=space_admin)
        space.add_member(posting_user)

        post = posting_user.create_community_encircled_post(
            space.id,
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            image=SimpleUploadedFile(name=image_name, content=simple_jpeg_bytes),
            visibility=VisibilityType.MEMBERS.value,
        )
        PostUserMention.create_post_user_mention(user=space_admin, post=post)
        PostComment.create_comment(text=make_fake_post_text(), post=post, commenter=posting_user)

        response = self.delete_space_post(post.id, space_admin)

        assert response.data is None
        assert response.errors is not None
        assert "Bad user input" == str(response.errors[0].message)

        query_post = Post.objects.get(id=post.id)
        assert query_post.id == post.id
        assert query_post.title == post.title

        assert PostUserMention.objects.filter(post=post).count() == 1
        assert PostComment.objects.filter(post=post).count() == 1
        assert PostImage.objects.filter(post=post).count() == 1

    def delete_space_post(self, post_id, user):
        return schema.execute_sync(
            """
                mutation Mutation($id: UUID!) {
                    deleteSpacePost(id: $id) {
                        id
                        title
                        posts {
                            totalResults
                        }
                    }
                }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={
                "id": str(post_id),
            },
        )

    def test_insights_by_user_id_success_user_anonymous(self):
        insight_user = make_user()
        insight_user_2 = make_user()

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight  Foo",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=now,
        )
        insight2 = Insight.objects.create(
            creator=insight_user, title="Insight 2", date_published=now - timezone.timedelta(days=1)
        )
        insight3 = Insight.objects.create(creator=insight_user_2, title="Insight 3", date_published=now)

        response = schema.execute_sync(
            f"""
            query {{
                insightsByUserId(id: "{insight_user.username}") {{
                    data {{
                        id
                        title
                        headerImage
                    }}
                    totalResults
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        assert response.errors is None
        insights = response.data["insightsByUserId"]["data"]
        assert len(insights) == 2

        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert insight1_result["headerImage"] == insight1.header_image

        insight2_result = insights[1]
        assert insight2_result["title"] == insight2.title

        assert insight3.title not in [insight["title"] for insight in insights]

    def test_insights_by_user_id_success_user_authenticated(self):
        insight_user = make_user()
        insight_user_2 = make_user()

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight  Foo",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=now,
        )
        insight2 = Insight.objects.create(
            creator=insight_user, title="Insight 2", date_published=now - timezone.timedelta(days=1)
        )
        insight3 = Insight.objects.create(creator=insight_user_2, title="Insight 3", date_published=now)

        response = schema.execute_sync(
            f"""
            query {{
                insightsByUserId(id: "{insight_user.username}") {{
                    data {{
                        id
                        title
                        headerImage
                    }}
                    totalResults
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": insight_user_2}}),
        )

        assert response.errors is None
        insights = response.data["insightsByUserId"]["data"]
        assert len(insights) == 2

        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert insight1_result["headerImage"] == insight1.header_image

        insight2_result = insights[1]
        assert insight2_result["title"] == insight2.title

        assert insight3.title not in [insight["title"] for insight in insights]

    def test_insights_by_user_id_error_blocked_user(self):
        insight_user = make_user()
        insight_user_2 = make_user()

        insight_user_2.block_user_with_id(insight_user.id)

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight  Foo",
            header_image=SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes),
            date_published=now,
        )
        insight2 = Insight.objects.create(
            creator=insight_user, title="Insight 2", date_published=now - timezone.timedelta(days=1)
        )
        insight3 = Insight.objects.create(creator=insight_user_2, title="Insight 3", date_published=now)

        response = schema.execute_sync(
            f"""
            query {{
                insightsByUserId(id: "{insight_user.username}") {{
                    data {{
                        id
                        title
                        headerImage
                    }}
                    totalResults
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": insight_user_2}}),
        )

        assert response.data is None
        assert len(response.errors) == 1
        assert "User not found" == str(response.errors[0].message)

    def test_select_last_insights(self):
        insight_user = make_user()
        posting_user = make_user()
        other_user = make_user()
        private_user = make_user()

        post_text_public = make_fake_post_text()
        post_title_public = make_fake_post_title()
        post_text_draft = make_fake_post_text()
        post_title_draft = make_fake_post_title()

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight 1",
            date_published=now,
        )

        post1 = posting_user.create_public_post(
            text=post_text_public,
            title=post_title_public,
        )
        post2 = posting_user.create_public_post(
            text=post_text_public,
            title=post_title_public,
        )
        post3 = posting_user.create_public_post(text=post_text_draft, title=post_title_draft, is_draft=True)
        post_private = private_user.create_encircled_post(
            circles_ids=[private_user.connections_circle_id], text="private post", title="private post"
        )
        insight1.posts.add(post1, post2, post3, post_private)

        insight2 = Insight.objects.create(
            id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            creator=posting_user,
            title="Insight 2",
            date_published=now - timezone.timedelta(days=1),
        )
        post4 = posting_user.create_public_post(
            text=post_text_public,
            title=post_title_public,
        )
        post4.comment(text=post_text_public, commenter=other_user)
        insight2.posts.add(post4)

        insight3 = Insight.objects.create(
            id="00000000-0000-0000-0000-000000000001",
            creator=posting_user,
            title="Insight 3",
            date_published=now - timezone.timedelta(days=1),
        )
        post5 = posting_user.create_public_post(
            text=post_text_public,
            title=post_title_public,
        )
        insight3.posts.add(post5)

        insight4 = Insight.objects.create(
            id="00000000-0000-0000-0000-000000000000",
            creator=posting_user,
            title="Insight 4",
            date_published=now - timezone.timedelta(days=2),
        )

        response = schema.execute_sync(
            f"""
            query {{
                lastInsights {{
                    data {{
                        title
                        numberOfPosts
                        posts {{
                            title
                        }}
                        involvedUsers {{
                            totalResults
                            data {{
                              fullName
                            }}
                        }}
                    }}
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        insights = response.data["lastInsights"]["data"]
        assert len(insights) == 4
        # insight1 = next(i for i in insights if i["title"] == insight1_title)
        # insight2 = next(i for i in insights if i["title"] == insight2_title)
        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert insight1_result["numberOfPosts"] == 2
        assert insight1_result["posts"][0]["title"] == post_title_public
        assert insight1_result["posts"][1]["title"] == post_title_public
        assert insight1_result["involvedUsers"]["totalResults"] == 2

        insight2_result = insights[1]
        assert insight2_result["title"] == insight3.title
        assert insight2_result["numberOfPosts"] == 1
        assert insight2_result["involvedUsers"]["totalResults"] == 1

        insight3_result = insights[2]
        assert insight3_result["title"] == insight2.title
        assert insight3_result["numberOfPosts"] == 1
        assert insight3_result["involvedUsers"]["totalResults"] == 2

        insight4_result = insights[3]
        assert insight4_result["title"] == insight4.title
        assert insight4_result["numberOfPosts"] == 0
        assert insight4_result["involvedUsers"]["totalResults"] == 1

    def test_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")

        self.connect_to_user(following_user, followed_user)

        response = self.get_notifications(followed_user)
        assert response["totalResults"] >= 1
        notifications = response["data"]
        connection_requested_notification = next(n for n in notifications if n["notificationType"] == "CR")
        assert connection_requested_notification["owner"]["fullName"] == followed_user.profile.full_name()
        assert connection_requested_notification["options"]["user"]["fullName"] == following_user.profile.full_name()

        self.connect_to_user(followed_user, following_user)

        notifications = self.get_notifications(followed_user)["data"]
        connection_accepted_notification = next(n for n in notifications if n["notificationType"] == "CA")
        assert connection_accepted_notification["options"]["user"]["fullName"] == following_user.profile.full_name()

        notifications = self.get_notifications(following_user)["data"]
        connection_confirmed_notification = next(n for n in notifications if n["notificationType"] == "CC")
        assert connection_confirmed_notification["options"]["user"]["fullName"] == followed_user.profile.full_name()

    def test_community_new_post_notifications(self):
        post_user = make_user()
        subscriber_user = make_user()

        space = make_community(creator=post_user)
        space.add_member(subscriber_user)
        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=subscriber_user
        )

        post1 = post_user.create_community_encircled_post(
            text=make_fake_post_text(),
            title=make_fake_post_title(),
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )

        response = self.get_notifications(subscriber_user)
        assert response["totalResults"] == 1

        notification = response["data"][0]
        assert notification["options"]["post"]["title"] == post1.title
        assert notification["options"]["teaser"] == post1.title

        post2 = post_user.create_community_encircled_post(
            text=make_fake_post_text(),
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )

        response = self.get_notifications(subscriber_user)
        assert response["totalResults"] == 2

        notification = response["data"][0]
        assert notification["options"]["post"]["title"] is None
        expected_teaser = " ".join(post2.text.split()[:3]) + "..."
        assert notification["options"]["teaser"] == expected_teaser

    def test_community_admin_privileges_notifications(self):
        space_user = make_user()
        creator_user = make_user()

        space = make_community(creator=creator_user)
        space.add_member(space_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_user
        )

        creator_user.add_administrator_with_username_to_community_with_name(space_user.username, space.name)

        response = self.get_notifications(space_user)
        assert response["totalResults"] == 1

        notification = response["data"][0]

        assert notification["notificationType"] == "CAPG"
        assert notification["options"]["space"]["title"] == space.name
        assert notification["options"]["user"]["fullName"] == space_user.profile.full_name()

        creator_user.remove_administrator_with_username_from_community_with_name(space_user.username, space.name)

        response = self.get_notifications(space_user)
        assert response["totalResults"] == 2

        notification = response["data"][0]
        assert notification["notificationType"] == "CAPR"
        assert notification["options"]["space"]["title"] == space.name
        assert notification["options"]["user"]["fullName"] == space_user.profile.full_name()

    def test_has_new_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")
        following_user2 = make_user(name="Other2")

        assert self.has_new_notifications(followed_user)["status"] is False

        self.connect_to_user(following_user, followed_user)
        assert self.has_new_notifications(followed_user)["status"] is True

        self.disconnect_from_user(following_user, followed_user)
        assert self.has_new_notifications(followed_user)["status"] is False

        self.connect_to_user(following_user, followed_user)
        assert self.has_new_notifications(followed_user)["status"] is True

        data = self.get_notifications(followed_user)
        first_notification_id = data["data"][0]["id"]
        response = schema.execute_sync(
            """
            mutation LastSeenNotification($id: UUID!){
                lastSeenNotification(notificationId: $id) {
                    status
                }
            }
            """,
            variable_values={"id": str(first_notification_id)},
            context_value=BeneDict({"request": {"user": followed_user}}),
        )
        assert response.data["lastSeenNotification"]["status"] is False
        assert self.has_new_notifications(followed_user)["status"] is False

        self.connect_to_user(following_user2, followed_user)
        assert self.has_new_notifications(followed_user)["status"] is True

    def has_new_notifications(self, followed_user):
        response = schema.execute_sync(
            """
            query {
                hasNewNotifications {
                    status
                }
            }
            """,
            context_value=BeneDict({"request": {"user": followed_user}}),
        )
        assert response.errors is None
        data = response.data["hasNewNotifications"]
        return data

    def disconnect_from_user(self, following_user, followed_user):
        return self.connect_user(following_user, followed_user, UpdateConnectionAction.DISCONNECT)

    #
    def connect_to_user(self, following_user, followed_user):
        return self.connect_user(following_user, followed_user, UpdateConnectionAction.CONNECT)

    def connect_user(self, following_user, followed_user, action):
        connection_request_response = schema.execute_sync(
            """
            mutation UpdateConnectionWithUser($input: UpdateConnectionWithUserInput!) {
                updateConnectionWithUser(input: $input) {
                    id
                }
            }
            """,
            variable_values={
                "input": {
                    "userId": followed_user.username,
                    "action": action._value_,
                }
            },
            context_value=BeneDict({"request": {"user": following_user}}),
        )
        assert connection_request_response.errors is None
        return connection_request_response

    def test_filters_for_spaces(self):
        creator = make_user()
        topic1 = make_topic()
        topic2 = make_topic()
        # locations inside geolocation filter
        geolocation1 = geos.Point(8.5541567, 53.5101827, srid=4326)
        geolocation2 = geos.Point(8.5798387, 53.5590841, srid=4326)
        # location outside geolocation filter
        geolocation3 = geos.Point(9.76302, 53.5586627, srid=4326)
        space1 = make_community(
            creator=creator, topics=[topic1, topic2], location="Location1", geolocation=geolocation1
        )
        space2 = make_community(topics=[topic1], location="Location2", geolocation=geolocation2)
        space3 = make_community(topics=[topic2], location="Location3", geolocation=geolocation3)
        skill1 = make_skill()
        skill2 = make_skill()
        skill3 = make_skill()
        make_community_task(space1, skills=[skill1, skill2])
        make_community_task(space2, skills=[skill2, skill3])
        make_community_task(space3, skills=[skill3])

        filter_query = """
            query($topicId: UUID, $geolocation: GeoJSON, $skillIds: [UUID], $memberId: UUID) {
                spaces(topicId: $topicId, geolocation: $geolocation, skillIds: $skillIds, memberId: $memberId) {
                    totalResults
                    data {
                        id
                    }
                }
            }
        """

        def transform_space(space):
            return {"id": str(space.id)}

        def assert_filtered_spaces(filter_options, expected_spaces):
            filter_response = schema.execute_sync(filter_query, variable_values=filter_options)
            expected_data = list(map(transform_space, expected_spaces))
            self.assert_paged_results_equal(filter_response.data["spaces"], expected_data)

        # Return all spaces for empty filter
        assert_filtered_spaces({}, [space1, space2, space3])

        # Filter by common topic
        assert_filtered_spaces({"topicId": str(topic1.id)}, [space1, space2])

        # Filter by unique topic
        assert_filtered_spaces({"topicId": str(topic2.id)}, [space1, space3])

        # Filter by location
        assert_filtered_spaces({"geolocation": geolocation}, [space1, space2])

        # Filter by topic and location
        assert_filtered_spaces({"topicId": str(topic2.id), "geolocation": geolocation}, [space1])

        # Filter by single skill
        assert_filtered_spaces({"skillIds": [str(skill1.id)]}, [space1])

        # Filter by multiple skills
        assert_filtered_spaces({"skillIds": [str(skill1.id), str(skill2.id)]}, [space1, space2])

        # Filter by skills and location
        assert_filtered_spaces({"skillIds": [str(skill3.id)], "geolocation": geolocation}, [space2])

        # Filter by skills and topics
        assert_filtered_spaces({"skillIds": [str(skill2.id)], "topicId": str(topic2.id)}, [space1])

        # Filter by member id
        assert_filtered_spaces({"memberId": creator.username}, [space1])
        assert_filtered_spaces({"memberId": creator.username, "geolocation": geolocation}, [space1])

        # Filter by skills, topics and location
        assert_filtered_spaces(
            {
                "skillIds": [str(skill3.id)],
                "geolocation": geolocation,
                "topicId": str(topic2.id),
            },
            [],
        )

    def test_filters_for_discover_spaces(self):
        topic1 = make_topic()
        topic2 = make_topic()
        # locations inside geolocation filter
        geolocation1 = geos.Point(8.5541567, 53.5101827, srid=4326)
        geolocation2 = geos.Point(8.5798387, 53.5590841, srid=4326)
        # location outside geolocation filter
        geolocation3 = geos.Point(9.76302, 53.5586627, srid=4326)
        space1 = make_community(topics=[topic1, topic2], location="Location1", geolocation=geolocation1)
        space2 = make_community(topics=[topic1], location="Location2", geolocation=geolocation2)
        space3 = make_community(topics=[topic2], location="Location3", geolocation=geolocation3)
        skill1 = make_skill()
        skill2 = make_skill()
        skill3 = make_skill()
        make_community_task(space1, skills=[skill1, skill2])
        make_community_task(space2, skills=[skill2, skill3])

        filter_query = """
            query($topicIds: [UUID], $geolocation: GeoJSON, $skillIds: [UUID]) {
                discoverSpaces(topicIds: $topicIds, geolocation: $geolocation, skillIds: $skillIds) {
                    topicId
                    skillId
                    locationId
                    spaces {
                        totalResults
                        data {
                            id
                        }
                    }
                }
            }
        """

        def transform_space(space):
            return {"id": str(space.id)}

        def assert_filtered_spaces(filter_options, expected_spaces):
            filter_response = schema.execute_sync(
                filter_query,
                variable_values=filter_options,
                context_value=BeneDict({"request": {"user": AnonymousUser}}),
            )
            expected_data = list(map(transform_space, expected_spaces))
            self.assert_paged_results_equal(
                filter_response.data["discoverSpaces"][0]["spaces"],
                expected_data,
            )

        # Filter by common topic
        assert_filtered_spaces({"topicIds": [str(topic1.id)]}, [space1, space2])

        # Filter by unique topic
        assert_filtered_spaces({"topicIds": [str(topic2.id)]}, [space1, space3])

        filter_response = schema.execute_sync(
            filter_query,
            variable_values={
                "topicIds": [str(topic1.id), str(topic2.id)],
                "skillIds": [str(skill3.id)],
                "geolocation": geolocation,
            },
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )
        assert len(filter_response.data["discoverSpaces"]) == 4
        location, t1, t2, skill = (
            (0, 1, 2, 3) if filter_response.data["discoverSpaces"][1]["topicId"] == str(topic1.id) else (0, 2, 1, 3)
        )

        self.assert_paged_results_equal(
            filter_response.data["discoverSpaces"][location]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        self.assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t1]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        self.assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t2]["spaces"],
            list(map(transform_space, [space1, space3])),
        )
        self.assert_paged_results_equal(
            filter_response.data["discoverSpaces"][skill]["spaces"],
            list(map(transform_space, [space2])),
        )

    def test_sort_spaces_by_member_count(self):
        space1 = make_community()
        space2 = make_community()
        member = make_user()
        space1.add_member(member)

        filter_query = """
            query {
                spaces {
                    data {
                        id
                    }
                }
            }
        """
        response = schema.execute_sync(filter_query).data["spaces"]["data"]
        assert response[0]["id"] == str(space1.id)
        assert response[1]["id"] == str(space2.id)

    def test_my_spaces(self):
        creator1 = make_user()
        creator2 = make_user()
        space1 = make_community(creator=creator1)
        space2 = make_community(creator=creator2)
        space3 = make_community()
        space4 = make_community()
        creator1.join_community_with_name(space2.name)
        creator1.enable_new_post_notifications_for_community_with_name(space4.name)

        response = schema.execute_sync(
            """
            query {
                mySpaces {
                    section
                    type
                    spaces {
                        totalResults
                        data {
                            id
                        }
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": creator1}}),
        ).data["mySpaces"]

        assert len(response) == 3
        created_section = response[0]
        assert created_section["section"] == "Created"
        assert created_section["type"] == SpaceUserConnectionType.CREATOR.value
        assert created_section["spaces"]["totalResults"] == 1
        assert created_section["spaces"]["data"][0]["id"] == str(space1.id)
        joined_section = response[1]
        assert joined_section["section"] == "Joined"
        assert joined_section["type"] == SpaceUserConnectionType.MEMBER.value
        assert joined_section["spaces"]["totalResults"] == 1
        assert joined_section["spaces"]["data"][0]["id"] == str(space2.id)
        following_section = response[2]
        assert following_section["section"] == "Following"
        assert following_section["type"], SpaceUserConnectionType.FOLLOWER.value
        assert following_section["spaces"]["totalResults"] == 1
        assert following_section["spaces"]["data"][0]["id"] == str(space4.id)

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook.graphql_schema.publish_space_user_added_event")
    def test_space_membership_request_approval_process(
        self, mock_publish_space_user_added_event, mock_invalidate_discover_spaces_query_cache
    ):
        membership_requestor = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        mock_publish_space_user_added_event.return_value = None

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Preconditions
        pre_join_space = self.get_space_for_user(membership_requestor, space)
        assert pre_join_space["connectionStatusToMyself"] == []
        self.assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = self.get_notifications(membership_requestor)
        assert data["totalResults"] == 0
        data = self.get_notifications(space_creator)
        assert data["totalResults"] == 0

        # Send Join Request
        after_request_space = self.mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        assert len(after_request_space["connectionStatusToMyself"]), len(
            [SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value, SpaceUserConnectionType.FOLLOWER.value]
        )

        # Staff received MembershipRequest notification
        staff_request_received_notification = self.get_notifications(space_creator)["data"][0]
        assert staff_request_received_notification["notificationType"] == "CMR"
        assert staff_request_received_notification["options"]["space"]["title"] == space.title
        assert (
            staff_request_received_notification["options"]["user"]["fullName"]
            == membership_requestor.profile.full_name()
        )

        # Approve user
        space_after_approval = self.mutate_update_space_user_connection_data(
            auth_user=space_creator,
            user_id=membership_requestor.username,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBER,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        community = Community.objects.get(id=space.id)
        mock_publish_space_user_added_event.assert_called_once_with(
            username=membership_requestor.username, community=community
        )
        self.assert_paged_results_equal(
            space_after_approval["members"],
            [member_result(space_creator, is_admin=True), member_result(membership_requestor, is_admin=False)],
        )

        # User has correct connection status
        assert len(self.get_space_for_user(membership_requestor, space)["connectionStatusToMyself"]) == len(
            [SpaceUserConnectionType.MEMBER.value, SpaceUserConnectionType.FOLLOWER.value]
        )

        # User has approval notification
        membership_requestor_notifications = self.get_notifications(membership_requestor)
        assert membership_requestor_notifications["totalResults"] == 1
        assert membership_requestor_notifications["data"][0]["notificationType"] == "CMRA"

        # Staff has approval notification
        staff_notifications = self.get_notifications(space_creator)
        assert staff_notifications["totalResults"] == 1
        assert staff_notifications["data"][0]["notificationType"] == "CMRA"
        assert staff_notifications["data"][0]["options"]["space"]["title"] == space.title
        assert (
            staff_notifications["data"][0]["options"]["user"]["fullName"] == membership_requestor.profile.full_name()
        )

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook.graphql_schema.publish_space_user_added_event")
    def test_space_membership_request_rejection_process(
        self, mock_publish_space_user_added_event, mock_invalidate_discover_spaces_query_cache
    ):
        membership_requestor = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Preconditions
        pre_join_space = self.get_space_for_user(membership_requestor, space)
        assert pre_join_space["connectionStatusToMyself"] == []
        self.assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = self.get_notifications(membership_requestor)
        assert data["totalResults"] == 0
        data = self.get_notifications(space_creator)
        assert data["totalResults"] == 0

        # Send Join Request
        after_request_space = self.mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        assert len(after_request_space["connectionStatusToMyself"]) == len(
            [SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value, SpaceUserConnectionType.FOLLOWER.value]
        )

        # Staff received MembershipRequest notification
        staff_request_received_notification = self.get_notifications(space_creator)["data"][0]
        assert staff_request_received_notification["notificationType"] == "CMR"
        assert staff_request_received_notification["options"]["space"]["title"] == space.title
        assert (
            staff_request_received_notification["options"]["user"]["fullName"]
            == membership_requestor.profile.full_name()
        )

        # Approve user
        space_after_rejection = self.mutate_update_space_user_connection_data(
            auth_user=space_creator,
            user_id=membership_requestor.username,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.DISCONNECT,
        )

        self.assert_paged_results_equal(
            space_after_rejection["members"],
            [member_result(space_creator, is_admin=True)],
        )

        # User has correct connection status
        assert len(self.get_space_for_user(membership_requestor, space)["connectionStatusToMyself"]) == len(
            [SpaceUserConnectionType.FOLLOWER.value]
        )

        # User has no notification
        membership_requestor_notifications = self.get_notifications(membership_requestor)
        assert membership_requestor_notifications["totalResults"] == 0

        # Staff has no notification
        staff_notifications = self.get_notifications(space_creator)
        assert staff_notifications["totalResults"] == 0

        mock_publish_space_user_added_event.assert_not_called()

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_space_admin_grant_and_revoke_admin_access_success(self, mock_invalidate_discover_spaces_query_cache):
        space_member = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        space.add_member(space_member)

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Admin user grants admin privileges to a member user
        response = self.mutate_update_space_user_connection_data(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=space_member.username,
        )

        self.assert_paged_results_equal(
            response["members"],
            [member_result(space_creator, is_admin=True), member_result(space_member, is_admin=True)],
        )

        CommunityAdminPrivilegesGrantedNotification = get_community_admin_privileges_granted_notification_model()
        community_admin_privileges_granted_notifications = CommunityAdminPrivilegesGrantedNotification.objects.filter(
            granted_user=space_member
        )
        assert len(community_admin_privileges_granted_notifications) == 1
        notification = community_admin_privileges_granted_notifications.first()
        assert notification.community == space
        assert notification.notification.first().notification_type == "CAPG"

        # Admin user revokes admin privileges to an admin user
        response = self.mutate_update_space_user_connection_data(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_member.username,
        )

        self.assert_paged_results_equal(
            response["members"],
            [member_result(space_creator, is_admin=True), member_result(space_member, is_admin=False)],
        )

        CommunityAdminPrivilegesRevokedNotification = get_community_admin_privileges_revoked_notification_model()
        community_admin_privileges_revoked_notifications = CommunityAdminPrivilegesRevokedNotification.objects.filter(
            revoked_user=space_member
        )
        assert len(community_admin_privileges_revoked_notifications) == 1
        notification = community_admin_privileges_revoked_notifications.first()
        assert notification.community == space
        assert notification.notification.first().notification_type == "CAPR"

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_space_admin_grant_and_revoke_admin_access_errors(self, mock_invalidate_discover_spaces_query_cache):
        space_member = make_user()
        space_creator = make_user()
        space_admin = make_user()
        external_user = make_user()
        space = make_community(creator=space_creator)
        space.add_member(space_member)
        space.add_member(space_admin)
        space.add_administrator(space_admin)

        # Admin user cannot grant admin privileges to an admin user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=space_admin.username,
        )

        assert response.data is None
        assert response.errors is not None
        assert "User is already an administrator." in response.errors[0].extensions["errors"]
        assert (
            space.is_user_with_username_administrator_of_community_with_name(space_admin.username, space.name) is True
        )

        # Admin user cannot grant admin privileges to an external user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=external_user.username,
        )

        assert response.data is None
        assert response.errors is not None
        assert (
            "Cannot make administrator a user that is not part of the space."
            in response.errors[0].extensions["errors"]
        )
        assert space.is_user_with_username_member_of_community_with_name(external_user.username, space.name) is False

        # Admin user cannot revoke admin privileges to a member user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_member.username,
        )

        assert response.data is None
        assert response.errors is not None
        assert "User to remove is not an administrator." in response.errors[0].extensions["errors"]
        assert (
            space.is_user_with_username_administrator_of_community_with_name(space_member.username, space.name)
            is False
        )

        mock_invalidate_discover_spaces_query_cache.assert_called()

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_space_member_grant_and_revoke_admin_access_errors(self, mock_invalidate_discover_spaces_query_cache):
        member_user = make_user()
        member_user_2 = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        space.add_member(member_user)
        space.add_member(member_user_2)

        # Member user cannot grant admin privileges to a member user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=member_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=member_user_2.username,
        )

        assert response.data is None
        assert (
            "Only the administrators of the space can grant administrator privileges."
            in response.errors[0].extensions["errors"]
        )
        assert (
            space.is_user_with_username_administrator_of_community_with_name(member_user_2.username, space.name)
            is False
        )

        # Member user cannot revoke admin privileges to an admin user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=member_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_creator.username,
        )

        assert response.data is None
        assert (
            "Only the administrators of the space can revoke administrator privileges."
            in response.errors[0].extensions["errors"]
        )
        assert (
            space.is_user_with_username_administrator_of_community_with_name(member_user_2.username, space.name)
            is False
        )

        mock_invalidate_discover_spaces_query_cache.assert_called()

    def test_space_member_leaves_community_success(self):
        member_user = make_user()
        space_creator = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=member_user
        )

        response = self.mutate_update_space_user_connection_raw(
            auth_user=member_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBER,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is None
        assert response.data is not None

        memberships = space.memberships.all()
        assert len(memberships) == 1
        assert member_user not in memberships
        assert not CommunityNotificationsSubscription.objects.filter(community=space, subscriber=member_user).exists()

    def test_space_admin_leaves_community_success(self):
        space_creator = make_user()
        member_user_admin = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user_admin)
        space.add_administrator(member_user_admin)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_creator
        )

        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is None
        assert response.data is not None

        memberships = space.memberships.all()
        assert len(memberships) == 1
        assert space_creator not in memberships
        assert not CommunityNotificationsSubscription.objects.filter(
            community=space, subscriber=space_creator
        ).exists()

    def test_space_member_leaves_community_error_only_member(self):
        space_creator = make_user()

        space = make_community(creator=space_creator)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_creator
        )

        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBER,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is not None
        assert response.data is None
        assert "You cannot leave a community where you are the only member" in str(
            response.errors[0].extensions["errors"]
        )

        memberships = space.memberships.all()
        assert len(memberships) == 1
        assert CommunityNotificationsSubscription.objects.filter(community=space, subscriber=space_creator).exists()

    def test_space_admin_leaves_community_error_only_admin(self):
        space_creator = make_user()
        member_user_admin = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user_admin)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=space_creator
        )

        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.LEAVE_SPACE,
        )

        assert response.errors is not None
        assert response.data is None
        assert "You cannot leave a community where you are the only admin" in str(
            response.errors[0].extensions["errors"]
        )

        memberships = space.memberships.all()
        assert len(memberships) == 2

        assert CommunityNotificationsSubscription.objects.filter(community=space, subscriber=space_creator).exists()

    def test_remove_member_from_community_success(self):
        space_creator = make_user()
        member_user = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=member_user
        )

        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_creator,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REMOVE_MEMBER,
            user_id=member_user.username,
        )

        assert response.errors is None
        assert response.data is not None

        memberships = space.memberships.all().values_list("user__id", flat=True)
        assert len(memberships) == 1
        assert member_user not in memberships

        assert not CommunityNotificationsSubscription.objects.filter(community=space, subscriber=member_user).exists()
        CommunityMembershipRevokedNotification = get_community_membership_revoked_notification_model()
        community_membership_revoked_notifications = CommunityMembershipRevokedNotification.objects.filter(
            revoked_user=member_user
        )
        assert len(community_membership_revoked_notifications) == 1
        notification = community_membership_revoked_notifications.first()
        assert notification.community == space
        assert notification.notification.first().notification_type == "CMRE"

    def test_remove_member_from_community_error_only_admin(self):
        space_creator = make_user()
        member_user = make_user()
        request_user = make_user()

        space = make_community(creator=space_creator)
        space.add_member(member_user)
        space.add_member(request_user)

        CommunityNotificationsSubscription.enable_new_post_notification_for_community(
            community=space, subscriber=member_user
        )

        response = self.mutate_update_space_user_connection_raw(
            auth_user=request_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REMOVE_MEMBER,
            user_id=member_user.username,
        )

        assert response.errors is not None
        assert response.data is None

        assert "Only the administrators of the space can remove members" in str(
            response.errors[0].extensions["errors"]
        )

        memberships = space.memberships.all().values_list("user__id", flat=True)
        assert len(memberships) == 3
        assert member_user.id in memberships
        assert CommunityNotificationsSubscription.objects.filter(community=space, subscriber=member_user).exists()

        CommunityMembershipRevokedNotification = get_community_membership_revoked_notification_model()
        community_membership_revoked_notifications = CommunityMembershipRevokedNotification.objects.filter(
            revoked_user=member_user
        )
        assert len(community_membership_revoked_notifications) == 0

    def test_space_with_posts(self):
        user_member = make_user()
        user_external = make_user()
        space = make_community(creator=user_member)

        public_posts = [
            user_member.create_public_post(text=make_fake_post_text(), title=make_fake_post_title()) for _ in range(5)
        ]
        for post in public_posts:
            post.community = space
            post.save()
        public_ids = [str(post.id) for post in public_posts]

        private_posts = [
            user_member.create_encircled_post(
                circles_ids=[user_member.connections_circle_id],
                text=make_fake_post_text(),
                title=make_fake_post_title(),
            )
            for _ in range(3)
        ]
        for post in private_posts:
            post.community = space
            post.save()
        private_ids = [str(post.id) for post in private_posts]

        # member user with visibility all shows all posts
        data = self.get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.ALL)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["hasPublicPosts"] == True
        assert data["hasPrivatePosts"] == True
        assert data["posts"]["totalResults"] == len(public_posts) + len(private_posts)
        assert len(self.private_post_ids(posts_data)) == len(private_ids)
        assert len(self.public_post_ids(posts_data)) == len(public_ids)
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # member user with visibility public posts shows only public posts
        data = self.get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.PUBLIC)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(public_posts)
        assert len(self.public_post_ids(posts_data)) == len(public_ids)
        assert len(self.private_post_ids(posts_data)) == 0
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # member user with visibility private posts shows only private posts
        data = self.get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.MEMBERS)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(private_posts)
        assert len(self.public_post_ids(posts_data)) == 0
        assert len(self.private_post_ids(posts_data)) == len(private_ids)
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # external user without visibility filter shows public posts
        data = self.get_space_by_id_with_posts(user_external, space.id)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(public_posts)
        assert len(self.public_post_ids(posts_data)) == len(public_ids)
        assert len(self.private_post_ids(posts_data)) == 0
        assert posts_data[0]["created"] >= posts_data[1]["created"]

        # external user visibility filter is ignored and shows public posts
        data = self.get_space_by_id_with_posts(user_external, space.id, VisibilityFilter.MEMBERS)
        posts_data = data["posts"]["data"]
        assert data["id"] == str(space.id)
        assert data["posts"]["totalResults"] == len(public_posts)
        assert len(self.public_post_ids(posts_data)) == len(public_ids)
        assert len(self.private_post_ids(posts_data)) == 0
        assert posts_data[0]["created"] >= posts_data[1]["created"]

    def test_space_with_sorted_members(self):
        # Create space and members
        admin1 = make_user(name="Xenia", last_name="Admin")
        admin2 = make_user(name="John", last_name="Admin")
        user1 = make_user(name="Angela", last_name="User")
        user2 = make_user(name="Angela", last_name="Member")
        user3 = make_user(name="Another", last_name="User")
        space = make_community(creator=admin1)
        space.add_member(admin2)
        space.add_administrator(admin2)
        space.add_member(user1)
        space.add_member(user2)
        space.add_member(user3)

        response = schema.execute_sync(
            """
            query($id:String!) {
                spaceById(idOrName:$id) {
                    members {
                        totalResults
                        data {
                            user {
                                fullName
                            }
                        }
                    }
                }
            }
            """,
            variable_values={"id": str(space.id)},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        # Check sort order of members: First by membership (admins before members), then by full name
        assert response.errors is None
        paged_members = response.data["spaceById"]["members"]
        assert paged_members["totalResults"] == 5
        members = paged_members["data"]
        assert members[0]["user"]["fullName"] == "John Admin"
        assert members[1]["user"]["fullName"] == "Xenia Admin"
        assert members[2]["user"]["fullName"] == "Angela Member"
        assert members[3]["user"]["fullName"] == "Angela User"
        assert members[4]["user"]["fullName"] == "Another User"

    @staticmethod
    def public_post_ids(posts_data):
        return [post_data["id"] for post_data in posts_data if post_data["isPublic"]]

    @staticmethod
    def private_post_ids(posts_data):
        return [post_data["id"] for post_data in posts_data if not post_data["isPublic"]]

    def test_report_post(self):
        posting_user = make_user()
        posting_user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )

        response = schema.execute_sync(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": reporting_user}}),
            variable_values=BeneDict(
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

        post_data = self.get_post_with_id_data(post, reporting_user)
        assert post_data["id"] == str(post.id)

        post_data = self.get_post_with_id_data(post, other_user)
        assert post_data["id"] == str(post.id)

        approve_verify_moderated_object(post.id, posting_user)

        response = self.get_post_with_id_raw(post, other_user)
        assert other_user.can_see_post(post) is False
        assert response.data["postById"] is None

    def test_report_post_comment(self):
        posting_user = make_user()
        posting_user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        comment = post.comment(text=f"comment text 1 @{posting_user.username}", commenter=posting_user)

        response = schema.execute_sync(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": reporting_user}}),
            variable_values=BeneDict(
                {
                    "objectId": str(comment.id),
                    "contentType": ContentType.POST_COMMENT.value,
                    "description": "report",
                }
            ),
        )

        assert response.errors is None
        assert response.data["reportContent"]["success"] is True

        post_data = self.get_post_with_id_data(post, reporting_user)
        assert len(post_data["comments"]) == 1

        approve_verify_moderated_object(comment.id, posting_user)

        post_data = self.get_post_with_id_data(post, other_user)
        assert len(post_data["comments"]) == 0

    @pytest.mark.skip("Fundamentally broken on Postgres, even though this test would work")
    def test_report_user(self):
        user = make_user()
        user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        user_before_report = self.get_user_with_id_data(user, reporting_user)
        assert user_before_report["id"] == user.username

        user_before_report = self.get_user_with_id_data(user)
        assert user_before_report["id"] == user.username

        response = schema.execute_sync(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": reporting_user}}),
            variable_values=BeneDict(
                {
                    "objectId": str(user.username),
                    "contentType": ContentType.USER.value,
                    "description": "report",
                }
            ),
        )

        assert response.errors is None
        assert response.data["reportContent"]["success"] is True

        response = self.get_user_with_id_raw(user, reporting_user)
        assert response.data is None

        user_before_approve = self.get_user_with_id_data(user, other_user)
        assert user_before_approve["id"] == user.username
        user_before_approve = self.get_user_with_id_data(user)
        assert user_before_approve["id"] == user.username

        approve_verify_moderated_object(user.id, user)

        response_after_approve = self.get_user_with_id_raw(user, other_user)
        assert response_after_approve.data["userById"] is None
        response_after_approve = self.get_user_with_id_raw(user)
        assert response_after_approve.data["userById"] is None

    def test_report_space(self):
        space_user = make_user()
        space_user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        space = make_community(creator=space_user)

        response = schema.execute_sync(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": reporting_user}}),
            variable_values=BeneDict(
                {
                    "objectId": str(space.id),
                    "contentType": ContentType.SPACE.value,
                    "description": "report",
                }
            ),
        )

        assert response.errors is None
        assert response.data["reportContent"]["success"] is True

        response = schema.execute_sync(
            f"""
            query {{
                spaceById(idOrName: "{space.id}") {{
                    id
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": reporting_user}}),
        )
        assert response.errors is None
        assert len(response.data["spaceById"]) == 1
        assert response.data["spaceById"]["id"] == str(space.id)

        response = schema.execute_sync(
            f"""
            query {{
                spaceById(idOrName: "{space.name}") {{
                    name
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": other_user}}),
        )
        assert response.errors is None
        assert len(response.data["spaceById"]) == 1
        assert response.data["spaceById"]["name"] == str(space.name)

        approve_verify_moderated_object(space.id, space_user)

        response = schema.execute_sync(
            f"""
            query {{
                spaceById(idOrName: "{space.id}") {{
                    id
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": other_user}}),
        )
        assert response.data["spaceById"] is None

    def test_block_user(self):
        blocking_user = make_user(name="BlockingUser")
        two_hours_ago = datetime.now() - timedelta(hours=2)
        blocked_user = make_user(name="BlockedUser", date_joined=two_hours_ago)
        other_user = make_user(name="OtherUser", date_joined=two_hours_ago)
        other_user.save()

        other_post = other_user.create_public_post(
            text=(make_fake_post_text()),
            title=(make_fake_post_title()),
        )
        other_post.comment(text=f"comment text 1", commenter=blocked_user)

        blocked_post = blocked_user.create_public_post(
            text=(make_fake_post_text()),
            title=(make_fake_post_title()),
        )
        blocked_post.comment(text=f"comment text 1", commenter=other_user)

        response = schema.execute_sync(
            """
            query {
                userSuggestions(limit:100) {
                    totalResults
                    data {
                        fullName
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": blocking_user}}),
        )
        assert response.data["userSuggestions"]["totalResults"] == 2

        response = schema.execute_sync(
            """
            mutation ($userId: UUID!) {
                blockUser(userId: $userId) {
                    success
                }
            }
            """,
            context_value=BeneDict({"request": {"user": blocking_user}}),
            variable_values=BeneDict(
                {
                    "userId": blocked_user.username,
                }
            ),
        )

        blocked_post_raw = self.get_post_with_id_raw(blocked_post, blocking_user)
        assert blocked_post_raw.data["postById"] is None
        other_post_data = self.get_post_with_id_data(other_post, blocking_user)
        assert other_post_data["involvedUsers"]["totalResults"] == 1
        assert other_post_data["numberOfComments"] == 0
        assert other_post_data["commenters"]["totalResults"] == 0

        assert response.errors is None
        assert response.data["blockUser"]["success"] is True

        response_after_blocking = self.get_user_with_id_raw(blocked_user, blocking_user)
        assert response_after_blocking.data["userById"] is None

        response_after_blocking = self.get_user_with_id_raw(blocking_user, blocked_user)
        assert response_after_blocking.data["userById"] is None

        response = schema.execute_sync(
            """
            query {
                userSuggestions(limit:100) {
                    totalResults
                    data {
                        fullName
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": blocking_user}}),
        )
        assert response.data["userSuggestions"]["totalResults"] == 1
        assert response.data["userSuggestions"]["data"][0]["fullName"] == "OtherUser"

    # Utility methods

    def get_user_with_id_data(self, user_to_get, calling_user=None):
        response = self.get_user_with_id_raw(user_to_get, calling_user)
        assert response.errors is None
        return response.data["userById"]

    def get_user_with_id_raw(self, user_to_get, calling_user=None):
        return schema.execute_sync(
            f"""
            query {{
                userById(id: "{user_to_get.username}") {{
                    id
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": calling_user or AnonymousUser}}),
        )

    def get_post_with_id_data(self, post, user=None):
        response = self.get_post_with_id_raw(post, user)
        assert response.errors is None
        return response.data["postById"]

    def get_post_with_id_raw(self, post, user=None):
        return schema.execute_sync(
            f"""
            query {{
                postById(id: "{post.id}") {{
                    id
                    text
                    title
                    image {{
                        url
                        width
                        height
                    }}
                    created
                    creator {{
                        id
                    }}
                    comments {{
                        text
                        mentions {{
                            fullName
                        }}
                        myReaction {{
                            HEART
                        }}
                        reactions {{
                            HEART
                        }}
                    }}
                    mentions {{
                        fullName
                    }}
                    numberOfComments
                    involvedUsers {{
                        totalResults
                        data {{
                            firstName
                        }}
                    }}
                    commenters {{
                        totalResults
                        data {{
                            firstName
                        }}
                    }}
                    myReaction {{
                        HEART
                    }}
                    reactions {{
                        HEART
                    }}
                }}
            }}
            """,
            context_value=BeneDict({"request": {"user": user or AnonymousUser}}),
        )

    def mutate_update_space_user_connection_raw(
        self,
        auth_user: User,
        space_id: UUID,
        connection_type: SpaceUserConnectionType,
        connect_action: UpdateConnectionAction,
        user_id: Optional[UUID] = None,
    ):
        return schema.execute_sync(
            """
            mutation ($spaceId: UUID!, $userId: UUID, $type: SpaceUserConnectionType!, $action: UpdateConnectionAction!){
                updateSpaceUserConnection(spaceId: $spaceId,
                                            userId: $userId,
                                            connectionType: $type,
                                            connectAction: $action) {
                    id
                    name
                    members {
                        totalResults
                        data {
                            user {
                                id
                            }
                            isAdministrator
                        }
                    }
                    connectionStatusToMyself
                }
            }
            """,
            context_value=BeneDict({"request": {"user": auth_user}}),
            variable_values=BeneDict(
                {
                    "spaceId": str(space_id),
                    "userId": str(user_id) if user_id else None,
                    "type": connection_type.value,
                    "action": connect_action.value,
                }
            ),
        )

    def mutate_update_space_user_connection_data(
        self,
        auth_user: User,
        space_id: UUID,
        connection_type: SpaceUserConnectionType,
        connect_action: UpdateConnectionAction,
        user_id: Optional[UUID] = None,
    ):
        response = self.mutate_update_space_user_connection_raw(
            auth_user, space_id, connection_type, connect_action, user_id
        )
        assert response.errors is None
        return response.data["updateSpaceUserConnection"]

    def get_space_for_user(self, user: User, space: Community):
        response = schema.execute_sync(
            """
            query($id:String!) {
                spaceById(idOrName:$id) {
                    id
                    name
                    members {
                        totalResults
                        data {
                            user {
                                id
                            }
                            isAdministrator
                        }
                    }
                    connectionStatusToMyself
                }
            }
            """,
            variable_values={"id": str(space.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.errors is None
        return response.data["spaceById"]

    def get_space_by_id_with_posts(self, user: User, id: UUID, visibility: VisibilityFilter = VisibilityFilter.ALL):
        response = schema.execute_sync(
            """
            query($id:String!, $visibility:VisibilityFilter!) {
                spaceById(idOrName:$id) {
                    id
                    name
                    hasPublicPosts
                    hasPrivatePosts
                    posts(visibility:$visibility) {
                        totalResults
                        data {
                            id
                            title
                            isPublic
                            created
                        }
                    }
                }
            }
            """,
            variable_values={"id": str(id), "visibility": visibility.value},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.errors is None
        return response.data["spaceById"]

    def get_notifications(self, user):
        response = schema.execute_sync(
            """
            query {
                notifications {
                    totalResults
                    data {
                        id
                        owner {
                            fullName
                        }
                        created
                        read
                        notificationType
                        options {
                            user {
                                fullName
                            }
                            post {
                                title
                            }
                            postComment {
                                text
                            }
                            space {
                                title
                            }
                            teaser
                        }
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
        )
        assert response.errors is None
        return response.data["notifications"]

    def assert_paged_results_equal(self, results: dict, expected_data: List[dict[str, any]]):
        assert results["totalResults"] == len(expected_data)

        for el in expected_data:
            assert el in results["data"]

    def test_spaces_missing_required_fields_do_not_pass_validation(self):
        user = make_user()

        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            validate_space_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": {}},
        )

        field_errors = json.loads(str(response.errors[0].extensions["errors"]))
        assert "required" == field_errors["title"][0]["code"]
        assert "required" == field_errors["description"][0]["code"]
        assert response.data is None

    def test_invalid_spaces_do_not_pass_validation(self):
        user = make_user()
        topic_ids = [str(make_topic().id) for _ in range(7)]
        empty_image = SimpleUploadedFile(name="cover.jpg", content="")

        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid"}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "title", "value": None, "expected_code": "null"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "  ", "expected_code": "blank"},
            {"field": "title", "value": "f", "expected_code": "min_length"},
            {"field": "title", "value": "f" * 61, "expected_code": "max_length"},
            {"field": "description", "value": None, "expected_code": "null"},
            {"field": "description", "value": "", "expected_code": "blank"},
            {"field": "description", "value": "f" * 601, "expected_code": "max_length"},
            {"field": "topics", "value": None, "expected_code": "null"},
            {"field": "topics", "value": [], "expected_code": "min_length"},
            {"field": "topics", "value": topic_ids, "expected_code": "max_length"},
            {
                "field": "topics",
                "value": [invalid_uuid],
                "expected_error": f"No topic with the id '{invalid_uuid}' found.",
            },
            {"field": "cover", "value": None, "expected_code": "null"},
            {"field": "cover", "value": {}, "expected_code": "invalid"},
            {"field": "cover", "value": "", "expected_code": "invalid"},
            {"field": "cover", "value": "foobar", "expected_code": "invalid"},
            {"field": "cover", "value": empty_image, "expected_code": "empty"},
            {"field": "cover", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "cover", "value": create_video_file(), "expected_code": "invalid_image"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                validate_space_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            assert (response.errors, testCase) is not None
            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert response.data is None

    def test_valid_partial_spaces_pass_validation(self):
        user = make_user()
        valid_input = {"title": "valid", "description": "valid"}
        topic_ids = [str(make_topic().id) for _ in range(2)]
        cover = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        sdg_ids = [str(make_sdg().id) for _ in range(2)]
        location = "Hamburg, Germany"
        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """

        valid_inputs = [
            valid_input,
            valid_input | {"topics": topic_ids},
            valid_input | {"cover": cover},
            valid_input | {"sdgs": sdg_ids},
            valid_input | {"location": location},
            valid_input | {"topics": topic_ids, "cover": cover, "sdgs": sdg_ids, "location": location},
            valid_input | {"topics": topic_ids, "cover": cover, "sdgs": []},
        ]

        for input in valid_inputs:
            response = schema.execute_sync(
                validate_space_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": input},
            )

            assert response.data["validateSpace"]["success"] is True
            assert response.errors is None

    def test_can_not_validate_space_if_not_logged_in(self):
        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput!) {
                validateSpace(input: $input) {
                    success
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid"}

        response = schema.execute_sync(
            validate_space_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def assert_is_unauthorized(self, response):
        assert response.data is None
        assert "Unauthorized" in str(response.errors[0].message)
        assert "UNAUTHORIZED" == str(response.errors[0].extensions["code"])

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook.graphql_schema.publish_space_created_event")
    def test_can_not_create_spaces_missing_required_fields(
        self, mock_publish_space_created_event, mock_invalidate_discover_spaces_query_cache
    ):
        user = make_user()
        topic_ids = [str(make_topic().id) for _ in range(7)]
        valid_topics = topic_ids[:2]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
            """

        expectedErrors = [
            {
                "input": {"title": "valid", "description": "valid", "topics": valid_topics},
                "expected_error": "was not provided",
            },
            {
                "input": {"title": "valid", "description": "valid", "cover": valid_image},
                "expected_error": "was not provided",
            },
            {
                "input": {"title": "valid", "topics": valid_topics, "cover": valid_image},
                "expected_error": "was not provided",
            },
            {
                "input": {"description": "valid", "topics": valid_topics, "cover": valid_image},
                "expected_error": "was not provided",
            },
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                create_space_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": testCase["input"]},
            )

            assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createSpace"] if response.data else response.data) is None

        mock_publish_space_created_event.assert_not_called()
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    def test_validates_space_before_creation(self):
        user = make_user()
        topic_ids = [str(make_topic().id) for _ in range(7)]
        valid_topics = topic_ids[:2]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        empty_image = SimpleUploadedFile(name="cover.jpg", content="")

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid", "topics": valid_topics, "cover": valid_image}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "title", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "f", "expected_code": "min_length"},
            {"field": "title", "value": "f" * 61, "expected_code": "max_length"},
            {"field": "description", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "description", "value": "", "expected_code": "blank"},
            {"field": "description", "value": "f" * 601, "expected_code": "max_length"},
            {"field": "topics", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "topics", "value": [], "expected_code": "min_length"},
            {"field": "topics", "value": topic_ids, "expected_code": "max_length"},
            {
                "field": "topics",
                "value": [invalid_uuid],
                "expected_error": f"No topic with the id '{invalid_uuid}' found.",
            },
            {"field": "cover", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "cover", "value": {}, "expected_code": "invalid"},
            {"field": "cover", "value": "", "expected_code": "invalid"},
            {"field": "cover", "value": "foobar", "expected_code": "invalid"},
            {"field": "cover", "value": empty_image, "expected_code": "empty"},
            {"field": "cover", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "cover", "value": create_video_file(), "expected_code": "invalid_image"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                create_space_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createSpace"] if response.data else response.data) is None

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook.graphql_schema.publish_space_created_event")
    def test_can_create_space(self, mock_publish_space_created_event, mock_invalidate_discover_spaces_query_cache):
        user = make_user()
        topic_ids = [str(make_topic().id) for _ in range(2)]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                    name
                    title
                    description
                    topics { id }
                    cover
                    members {
                        data {
                            user {id}
                            isAdministrator
                        }
                    }
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid", "topics": topic_ids, "cover": valid_image}

        response = schema.execute_sync(
            create_space_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        created_space = response.data["createSpace"]
        assert "id" in created_space
        assert "valid" == created_space["name"]
        assert "valid" == created_space["title"]
        assert "valid" == created_space["description"]
        assert len(topic_ids) == len(created_space["topics"])
        for topic in created_space["topics"]:
            assert topic["id"] in topic_ids
        assert "cover.jpg" in created_space["cover"]

        # Verify that creator is admin
        assert 1 == len(created_space["members"]["data"])
        member = created_space["members"]["data"][0]
        assert str(user.username) == member["user"]["id"]
        assert member["isAdministrator"] is True

        community = Community.objects.get(id=created_space["id"])
        mock_publish_space_created_event.assert_called_once_with(community=community)
        mock_invalidate_discover_spaces_query_cache.assert_called_once()

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    @mock.patch("openbook.graphql_schema.publish_space_created_event")
    def test_can_not_create_space_if_not_logged_in(
        self, mock_publish_space_created_event, mock_invalidate_discover_spaces_query_cache
    ):
        topic_ids = [str(make_topic().id) for _ in range(7)]
        valid_topics = topic_ids[:2]
        valid_image = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        create_space_mutation = """
            mutation test($input: CreateSpaceInput!) {
                createSpace(input: $input) {
                    id
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid", "topics": valid_topics, "cover": valid_image}

        response = schema.execute_sync(
            create_space_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)
        mock_publish_space_created_event.assert_not_called()
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    def test_validates_space_update(self):
        user = make_user()
        community = make_community()
        topic_ids = [str(make_topic().id) for _ in range(7)]
        empty_image = SimpleUploadedFile(name="cover.jpg", content="")

        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(community.id)}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "id", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "id", "value": invalid_uuid, "expected_error": "No community with the provided id exists."},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "f", "expected_code": "min_length"},
            {"field": "title", "value": "f" * 61, "expected_code": "max_length"},
            {"field": "description", "value": "", "expected_code": "blank"},
            {"field": "description", "value": "f" * 601, "expected_code": "max_length"},
            {"field": "topics", "value": [], "expected_code": "min_length"},
            {"field": "topics", "value": topic_ids, "expected_code": "max_length"},
            {
                "field": "topics",
                "value": [invalid_uuid],
                "expected_error": f"No topic with the id '{invalid_uuid}' found.",
            },
            {"field": "cover", "value": {}, "expected_code": "invalid"},
            {"field": "cover", "value": "", "expected_code": "invalid"},
            {"field": "cover", "value": "foobar", "expected_code": "invalid"},
            {"field": "cover", "value": empty_image, "expected_code": "empty"},
            {"field": "cover", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "cover", "value": create_video_file(), "expected_code": "invalid_image"},
            {"field": "avatar", "value": {}, "expected_code": "invalid"},
            {"field": "avatar", "value": "", "expected_code": "invalid"},
            {"field": "avatar", "value": "foobar", "expected_code": "invalid"},
            {"field": "avatar", "value": empty_image, "expected_code": "empty"},
            {"field": "avatar", "value": create_large_image_file(), "expected_code": "max_upload_size"},
            {"field": "avatar", "value": create_video_file(), "expected_code": "invalid_image"},
            {"field": "sdgs", "value": None, "expected_code": "null"},
            {
                "field": "sdgs",
                "value": [invalid_uuid],
                "expected_error": f"No sdg with the id '{invalid_uuid}' found.",
            },
            {"field": "location", "value": None, "expected_code": "null"},
            {"field": "contactDescription", "value": "f" * 101, "expected_code": "max_length"},
            {"field": "contactPhone", "value": "9" * 101, "expected_code": "max_length"},
            {"field": "contactEmail", "value": "invalid", "expected_code": "invalid"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                update_space_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={
                    "input": base_input | {testCase["field"]: testCase["value"]},
                },
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateSpace"] if response.data else response.data) is None

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_can_not_update_space_without_passing_id(self, mock_invalidate_discover_spaces_query_cache):
        user = make_user()
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """

        response = schema.execute_sync(
            update_space_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": {"title": "new title"}},
        )

        assert response.data is None
        assert "Field 'id' of required type 'UUID!' was not provided" in response.errors[0].message
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_can_update_space(self, mock_invalidate_discover_spaces_query_cache):
        user = make_user()
        community = make_community(creator=user)
        topic_ids = [str(make_topic().id) for _ in range(3)]
        cover = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        cover2 = SimpleUploadedFile(name="cover2.jpg", content=simple_jpeg_bytes)
        avatar = SimpleUploadedFile(name="avatar.jpg", content=simple_jpeg_bytes)
        avatar2 = SimpleUploadedFile(name="avatar2.jpg", content=simple_jpeg_bytes)
        sdg_ids = [str(make_sdg().id) for _ in range(3)]
        location = "Hamburg, Germany"
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(community.id)}
        valid_inputs = [
            {"title": "new title"},
            {"description": "new description"},
            {"topics": topic_ids[:2]},
            {"cover": cover},
            {"avatar": avatar},
            {"sdgs": sdg_ids[:2]},
            {"sdgs": []},
            {
                "title": "newest title",
                "description": "newest description",
                "topics": topic_ids,
                "cover": cover2,
                "avatar": avatar2,
                "sdgs": sdg_ids,
            },
            {"location": location},
            {"contactDescription": "Lorem ipsum"},
            {"contactPhone": "+49 123 12345"},
            {"contactEmail": "contact@space.com"},
            {"cover": None},
            {"avatar": None},
        ]

        for input in valid_inputs:
            response = schema.execute_sync(
                update_space_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": base_input | input},
            )

            assert str(community.id) == response.data["updateSpace"]["id"]
            assert response.errors is None

        mock_invalidate_discover_spaces_query_cache.assert_called()

    def test_updated_space_has_new_values(self):
        user = make_user()
        community = make_community(creator=user)
        topic_ids = [str(make_topic().id) for _ in range(2)]
        cover = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)
        avatar = SimpleUploadedFile(name="avatar.jpg", content=simple_jpeg_bytes)
        sdg_ids = [str(make_sdg().id) for _ in range(2)]
        location = "Hamburg, Germany"
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                    title
                    description
                    topics { id }
                    cover
                    avatar
                    sdgs { id }
                    location
                    contactDescription
                    contactPhone
                    contactEmail
                }
            }
            """
        input = {
            "id": str(community.id),
            "title": "newest title",
            "description": "newest description",
            "topics": topic_ids,
            "cover": cover,
            "avatar": avatar,
            "sdgs": sdg_ids,
            "location": location,
            "contactDescription": "Lorem ipsum",
            "contactPhone": "+49 123 12345",
            "contactEmail": "contact@space.com",
        }

        response = schema.execute_sync(
            update_space_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_space = response.data["updateSpace"]
        assert str(community.id) == updated_space["id"]
        assert "newest title" == updated_space["title"]
        assert "newest description" == updated_space["description"]
        assert len(topic_ids) == len(updated_space["topics"])
        for topic in updated_space["topics"]:
            assert topic["id"] in topic_ids
        assert "cover.jpg" in updated_space["cover"]
        assert "avatar.jpg" in updated_space["avatar"]
        assert len(sdg_ids) == len(updated_space["sdgs"])
        for sdg in updated_space["sdgs"]:
            assert sdg["id"] in sdg_ids
        assert "Hamburg, Germany" == updated_space["location"]
        assert "Lorem ipsum" == updated_space["contactDescription"]
        assert "+49 123 12345" == updated_space["contactPhone"]
        assert "contact@space.com" == updated_space["contactEmail"]

        # test space avatar and cover deletion
        input = {
            "id": str(community.id),
            "cover": None,
            "avatar": None,
        }

        response = schema.execute_sync(
            update_space_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_space = response.data["updateSpace"]
        assert str(community.id) == updated_space["id"]
        assert "" == updated_space["cover"]
        assert "" == updated_space["avatar"]

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_can_not_update_space_if_not_admin(self, mock_invalidate_discover_spaces_query_cache):
        user = make_user()
        community = make_community()
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """

        response = schema.execute_sync(
            update_space_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": {"id": str(community.id), "title": "new title"}},
        )

        assert response.data is None
        assert "Can't update a community that you do not administrate." in str(response.errors[0].extensions["errors"])

        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_can_not_update_space_if_not_logged_in(self, mock_invalidate_discover_spaces_query_cache):
        community = make_community()
        update_space_mutation = """
            mutation test($input: UpdateSpaceInput!) {
                updateSpace(input: $input) {
                    id
                }
            }
            """

        response = schema.execute_sync(
            update_space_mutation,
            variable_values={"input": {"id": str(community.id), "title": "new title"}},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)
        mock_invalidate_discover_spaces_query_cache.assert_not_called()

    @mock.patch("openbook.graphql_schema.publish_space_deleted_event")
    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_can_not_delete_space_if_not_admin(
        self, mock_invalidate_discover_spaces_query_cache, mock_publish_space_deleted_event
    ):
        user = make_user()
        community = make_community()
        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_space_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"id": str(community.id)},
        )

        assert response.data is None
        assert "Can't delete a community that you do not administrate." in str(response.errors[0].extensions["errors"])

        mock_invalidate_discover_spaces_query_cache.assert_not_called()
        mock_publish_space_deleted_event.assert_not_called()

    @mock.patch("openbook.graphql_schema.publish_space_deleted_event")
    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_can_not_delete_space_if_not_logged_in(
        self, mock_invalidate_discover_spaces_query_cache, mock_publish_space_deleted_event
    ):
        community = make_community()
        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_space_mutation,
            variable_values={"id": str(community.id)},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)
        mock_invalidate_discover_spaces_query_cache.assert_not_called()
        mock_publish_space_deleted_event.assert_not_called()

    @mock.patch("openbook.graphql_schema.publish_space_deleted_event")
    @mock.patch("openbook.graphql_schema.invalidate_discover_spaces_query_cache")
    def test_can_delete_space(self, mock_invalidate_discover_spaces_query_cache, mock_publish_space_deleted_event):
        user = make_user()
        community = make_community(creator=user)

        delete_space_mutation = """
            mutation test($id: UUID!) {
                deleteSpace(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_space_mutation,
            variable_values={"id": str(community.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data["deleteSpace"]["success"] is True
        assert response.errors is None

        mock_invalidate_discover_spaces_query_cache.assert_called_once()
        mock_publish_space_deleted_event.assert_called_once_with(community)

    def test_can_not_add_collaboration_tool_missing_required_fields(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_collection_type = "COLLABORATION"

        expectedErrors = [
            {
                "input": {"url": valid_url, "title": valid_title, "spaceId": valid_space_id},
                "expected_error": "was not provided",
            },
            {
                "input": {"url": valid_url, "spaceId": valid_space_id, "collectionType": valid_collection_type},
                "expected_error": "was not provided",
            },
            {
                "input": {"title": valid_title, "spaceId": valid_space_id, "collectionType": valid_collection_type},
                "expected_error": "was not provided",
            },
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                add_collaboration_tool_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": testCase["input"]},
            )

            assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addCollaborationTool"] if response.data else response.data) is None

    def test_validates_collaboration_tool_before_creation(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        expectedErrors = [
            {"field": "url", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "title", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "c", "expected_code": "min_length"},
            {"field": "title", "value": "c" * 61, "expected_code": "max_length"},
            {"field": "description", "value": "c", "expected_code": "min_length"},
            {"field": "description", "value": "c" * 101, "expected_code": "max_length"},
            {"field": "collectionType", "value": None, "expected_error": "Expected non-nullable type"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                add_collaboration_tool_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addCollaborationTool"] if response.data else response.data) is None

    def test_can_add_collaboration_tool(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                    url
                    title
                    description
                    collectionType
                    domain
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"
        valid_domain = "Holi"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        response = schema.execute_sync(
            add_collaboration_tool_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        added_collaboration_tool = response.data["addCollaborationTool"]
        assert "id" in added_collaboration_tool
        assert valid_url == added_collaboration_tool["url"]
        assert valid_title == added_collaboration_tool["title"]
        assert valid_description == added_collaboration_tool["description"]
        assert valid_collection_type in added_collaboration_tool["collectionType"]
        assert valid_domain in added_collaboration_tool["domain"]

    def test_can_not_add_collaboration_tool_if_not_logged_in(self):
        community = make_community()
        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """
        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        response = schema.execute_sync(
            add_collaboration_tool_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def test_can_not_add_collaboration_tool_if_not_space_member(self):
        user = make_user()
        community = make_community()

        add_collaboration_tool_mutation = """
            mutation test($input: AddCollaborationToolInput!) {
                addCollaborationTool(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "title": valid_title,
            "description": valid_description,
            "collectionType": valid_collection_type,
        }

        response = schema.execute_sync(
            add_collaboration_tool_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot add a collaboration tool to a community you are not a member of"
            in response.errors[0].extensions["errors"]
        )

    def test_can_not_delete_collaboration_tool_if_not_logged_in(self):
        collaboration_tool = make_collaboration_tool()

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def test_can_not_delete_collaboration_tool_if_not_space_member(self):
        collaboration_tool = make_collaboration_tool()
        user = make_user()

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot delete a collaboration tool in a community you are not a member of"
            in response.errors[0].extensions["errors"]
        )

    def test_can_delete_collaboration_tool_if_admin(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data["deleteCollaborationTool"]["success"] is True
        assert response.errors is None

    def test_can_delete_collaboration_tool_if_space_member(self):
        user = make_user()
        community = make_community()

        community.add_member(user)

        collaboration_tool = make_collaboration_tool(community=community)

        delete_collaboration_tool_mutation = """
            mutation test($id: UUID!) {
                deleteCollaborationTool(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_collaboration_tool_mutation,
            variable_values={"id": str(collaboration_tool.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data["deleteCollaborationTool"]["success"] is True
        assert response.errors is None

    def test_validates_collaboration_tool_before_update(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(collaboration_tool.id)}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "id", "value": None, "expected_error": "Expected non-nullable type"},
            {
                "field": "id",
                "value": invalid_uuid,
                "expected_error": "No collaboration tool with the provided id exists",
            },
            {"field": "url", "value": None, "expected_code": "null"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "title", "value": None, "expected_code": "null"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "c", "expected_code": "min_length"},
            {"field": "title", "value": "c" * 61, "expected_code": "max_length"},
            {"field": "description", "value": "c", "expected_code": "min_length"},
            {"field": "description", "value": "c" * 101, "expected_code": "max_length"},
            {"field": "collectionType", "value": None, "expected_code": "null"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                update_collaboration_tool_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={
                    "input": base_input | {testCase["field"]: testCase["value"]},
                },
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateSpace"] if response.data else response.data) is None

    def test_can_not_update_collaboration_tool_without_passing_id(self):
        user = make_user()
        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """

        response = schema.execute_sync(
            update_collaboration_tool_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": {"url": "https://holi.social/"}},
        )

        assert response.data is None
        assert "Field 'id' of required type 'UUID!' was not provided" in response.errors[0].message

    def test_can_not_update_collaboration_tool_if_not_space_member(self):
        user = make_user()
        collaboration_tool = make_collaboration_tool()

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """

        input = {"id": str(collaboration_tool.id), "url": "https://holi.social/"}

        response = schema.execute_sync(
            update_collaboration_tool_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.data is None
        assert "You cannot update a collaboration tool in a community you are not a member of" in str(
            response.errors[0].extensions["errors"]
        )

    def test_can_not_update_collaboration_tool_if_not_logged_in(self):
        collaboration_tool = make_collaboration_tool()

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """

        input = {"id": str(collaboration_tool.id), "url": "https://holi.social/"}

        response = schema.execute_sync(
            update_collaboration_tool_mutation,
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
            variable_values={"input": input},
        )

        self.assert_is_unauthorized(response)

    def test_can_update_collaboration_tool(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(collaboration_tool.id)}

        valid_url = "https://holi.social/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"

        valid_inputs = [
            {"url": valid_url},
            {"title": valid_title},
            {"description": valid_description},
            {"collectionType": valid_collection_type},
            {
                "url": valid_url,
                "title": valid_title,
                "description": valid_description,
                "collectionType": valid_collection_type,
            },
        ]

        for input in valid_inputs:
            response = schema.execute_sync(
                update_collaboration_tool_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": base_input | input},
            )

            assert str(collaboration_tool.id) == response.data["updateCollaborationTool"]["id"]
            assert response.errors is None

    def test_updated_collaboration_tool_has_new_values(self):
        user = make_user()
        community = make_community(creator=user)

        collaboration_tool = make_collaboration_tool(community=community)

        update_collaboration_tool_mutation = """
            mutation test($input: UpdateCollaborationToolInput!) {
                updateCollaborationTool(input: $input) {
                    id
                    url
                    title
                    description
                    collectionType
                }
            }
            """
        id = str(collaboration_tool.id)
        new_url = "https://holi.social/"
        new_title = "Project Holi"
        new_description = "holi is the network where people and organizations come together for the common good"
        new_collection_type = "COLLABORATION"

        input = {
            "id": id,
            "url": new_url,
            "title": new_title,
            "description": new_description,
            "collectionType": new_collection_type,
        }

        response = schema.execute_sync(
            update_collaboration_tool_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_collaboration_tool = response.data["updateCollaborationTool"]

        assert id == updated_collaboration_tool["id"]
        assert new_url == updated_collaboration_tool["url"]
        assert new_title == updated_collaboration_tool["title"]
        assert new_description == updated_collaboration_tool["description"]
        assert new_collection_type == updated_collaboration_tool["collectionType"]

    def test_can_not_create_task_missing_required_fields(self):
        user = make_user()

        community = make_community(creator=user)

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                }
            }
            """

        valid_input = {
            "name": "Valid name",
            "description": "Valid description",
            "spaceId": str(community.id),
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
        }
        expected_errors = {
            "name": "Field 'name' of required type 'String!' was not provided.",
            "description": "Field 'description' of required type 'String!' was not provided.",
            "spaceId": "Field 'spaceId' of required type 'UUID!' was not provided.",
            "visibility": "Field 'visibility' of required type 'VisibilityType!' was not provided.",
            "locationType": "Field 'locationType' of required type 'LocationType!' was not provided.",
            "regularity": "Field 'regularity' of required type 'Regularity!' was not provided.",
            "contactEmail": "Field 'contactEmail' of required type 'String!' was not provided.",
        }
        valid_input_keys = valid_input.keys()

        for input_key in valid_input_keys:
            test_input = copy.copy(valid_input)
            test_input.pop(input_key)
            response = schema.execute_sync(
                create_task_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": test_input},
            )

            assert expected_errors[input_key] in str(response.errors[0].message)
            assert (response.data["createTask"] if response.data else response.data) is None

    def test_validates_task_before_creation(self):
        user = make_user()

        community = make_community(creator=user)
        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                }
            }
            """

        non_existent_skill_id = str(uuid4())

        valid_input = {
            "spaceId": str(community.id),
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

        expectedErrors = [
            {"field": "spaceId", "value": str(uuid4()), "expected_error": "No community with the provided id exists."},
            {"field": "name", "value": "c", "expected_code": "min_length"},
            {"field": "name", "value": "c" * 400, "expected_code": "max_length"},
            {"field": "description", "value": "c" * 2000, "expected_code": "max_length"},
            {"field": "locationType", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "regularity", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactEmail", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactPhone", "value": "c" * 500, "expected_code": "max_length"},
            {
                "field": "skills",
                "value": [non_existent_skill_id],
                "expected_error": f"No skill with the id '{non_existent_skill_id}' found.",
            },
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                create_task_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createTask"] if response.data else response.data) is None

    def test_can_create_task(self):
        user = make_user()

        community = make_community(creator=user)
        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                    description
                    visibility
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"

        valid_input = {
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
        }

        response = schema.execute_sync(
            create_task_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        added_collaboration_tool = response.data["createTask"]
        assert "id" in added_collaboration_tool
        assert valid_name == added_collaboration_tool["name"]
        assert valid_description == added_collaboration_tool["description"]
        assert valid_visibility == added_collaboration_tool["visibility"]

    def test_can_not_create_task_if_not_logged_in(self):
        community = make_community()
        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "spaceId": str(community.id),
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

        response = schema.execute_sync(
            create_task_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def test_can_not_create_task_if_not_admin(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        skill = make_skill()

        create_task_mutation = """
            mutation test($input: CreateTaskInput!) {
                createTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "spaceId": str(community.id),
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

        response = schema.execute_sync(
            create_task_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": user}}),
        )

        field_errors = json.loads(response.errors[0].extensions["errors"])

        assert field_errors[0]["message"] in "You cannot add a task to a community you are not an administrator of"

    def test_can_not_update_task_missing_required_fields(self):
        user = make_user()

        community = make_community(creator=user)
        task = make_community_task(community)

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                }
            }
            """

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": "Valid name",
            "description": "Valid description",
            "visibility": "MEMBERS",
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
        }
        expected_errors = {
            "taskId": "Field 'taskId' of required type 'UUID!' was not provided.",
            "name": "Field 'name' of required type 'String!' was not provided.",
            "description": "Field 'description' of required type 'String!' was not provided.",
            "spaceId": "Field 'spaceId' of required type 'UUID!' was not provided.",
            "visibility": "Field 'visibility' of required type 'VisibilityType!' was not provided.",
            "locationType": "Field 'locationType' of required type 'LocationType!' was not provided.",
            "regularity": "Field 'regularity' of required type 'Regularity!' was not provided.",
            "contactEmail": "Field 'contactEmail' of required type 'String!' was not provided.",
        }
        valid_input_keys = valid_input.keys()

        for input_key in valid_input_keys:
            test_input = copy.copy(valid_input)
            test_input.pop(input_key)
            response = schema.execute_sync(
                update_task_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": test_input},
            )

            assert expected_errors[input_key] in str(response.errors[0].message)
            assert (response.data["updateTask"] if response.data else response.data) is None

    def test_validates_task_before_update(self):
        user = make_user()

        community = make_community(creator=user)
        task = make_community_task(community)
        skill = make_skill()

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                }
            }
            """

        non_existent_skill_id = str(uuid4())

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
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

        expectedErrors = [
            {"field": "taskId", "value": str(uuid4()), "expected_error": "No task with the provided id exists."},
            {"field": "spaceId", "value": str(uuid4()), "expected_error": "No community with the provided id exists."},
            {"field": "name", "value": "c", "expected_code": "min_length"},
            {"field": "name", "value": "c" * 400, "expected_code": "max_length"},
            {"field": "description", "value": "c" * 2000, "expected_code": "max_length"},
            {"field": "locationType", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "regularity", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactEmail", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "contactPhone", "value": "c" * 500, "expected_code": "max_length"},
            {
                "field": "skills",
                "value": [non_existent_skill_id],
                "expected_error": f"No skill with the id '{non_existent_skill_id}' found.",
            },
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                update_task_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["createTask"] if response.data else response.data) is None

    def test_can_update_task(self):
        user = make_user()

        community = make_community(creator=user)
        task = make_community_task(community)
        skill = make_skill()

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                    name
                    description
                    visibility
                    thumbnail
                }
            }
            """

        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"
        valid_thumbnail = SimpleUploadedFile(name="cover.jpg", content=simple_jpeg_bytes)

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
            "skills": [str(skill.id)],
            "slotsAvailable": 1,
            "location": "Hamburg, Germany",
            "contactPhone": "+49176176176176",
            "thumbnail": valid_thumbnail,
        }

        response = schema.execute_sync(
            update_task_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        updateTask = response.data["updateTask"]
        assert "id" in updateTask
        assert valid_name == updateTask["name"]
        assert valid_description == updateTask["description"]
        assert valid_visibility == updateTask["visibility"]
        assert "cover.jpg" in updateTask["thumbnail"]

        valid_name = "New valid name"
        valid_description = "New valid description"
        valid_visibility = "PUBLIC"

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": "HYBRID",
            "regularity": "REGULARLY",
            "contactEmail": "email@email.com",
            "thumbnail": None,
        }

        response = schema.execute_sync(
            update_task_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        updateTask = response.data["updateTask"]
        assert "id" in updateTask
        assert valid_name == updateTask["name"]
        assert valid_description == updateTask["description"]
        assert valid_visibility == updateTask["visibility"]
        assert "" == updateTask["thumbnail"]

    def test_can_not_update_task_if_not_logged_in(self):
        community = make_community()
        task = make_community_task(community)
        skill = make_skill()

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
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

        response = schema.execute_sync(
            update_task_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def test_can_not_update_task_if_not_admin(self):
        user = make_user()
        community = make_community()
        community.add_member(user)
        skill = make_skill()
        task = make_community_task(community)

        update_task_mutation = """
            mutation test($input: UpdateTaskInput!) {
                updateTask(input: $input) {
                    id
                    name
                }
            }
            """

        valid_input = {
            "taskId": str(task.id),
            "spaceId": str(community.id),
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

        response = schema.execute_sync(
            update_task_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data is None

        field_errors = json.loads(response.errors[0].extensions["errors"])

        assert field_errors[0]["message"] in "You cannot update a task of a community you are not an administrator of"

    def test_can_not_delete_task_if_not_space_admin(self):
        user = make_user()
        community = make_community()
        task = make_community_task(community)

        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_task_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"id": str(task.id)},
        )

        assert response.data is None
        assert "Can't delete a task within a community that you do not administrate." in str(
            response.errors[0].extensions["errors"]
        )

    def test_can_not_delete_task_if_not_logged_in(self):
        community = make_community()
        task = make_community_task(community)

        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_task_mutation,
            variable_values={"id": str(task.id)},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def test_can_delete_task(self):
        user = make_user()
        community = make_community(creator=user)
        task = make_community_task(community)

        delete_task_mutation = """
            mutation test($id: UUID!) {
                deleteTask(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_task_mutation,
            variable_values={"id": str(task.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data["deleteTask"]["success"] is True
        assert response.errors is None

    def test_space_with_tasks(self):
        user_member = make_user()
        user_external = make_user()
        space = make_community(creator=user_member)

        # create public task
        public_task = user_member.create_task(
            space_id=space.id,
            name="test_name_public",
            description="test_description",
            visibility=VisibilityType.PUBLIC,
            regularity="ONE_TIME",
            location_type="REMOTE",
            contact_email="test@test.com",
            slots_available=1,
        )

        # create members-only task
        user_member.create_task(
            space_id=space.id,
            name="test_name_private",
            description="test_description",
            visibility=VisibilityType.MEMBERS,
            regularity="ONE_TIME",
            location_type="REMOTE",
            contact_email="test@test.com",
            slots_available=1,
        )

        space_by_id_query = f"""
            query {{
                spaceById(idOrName: "{space.name}") {{
                    id
                    name
                    tasks {{
                        id
                        visibility
                    }}
                }}
            }}
            """

        # member should get all tasks
        response_member = schema.execute_sync(
            space_by_id_query,
            context_value=BeneDict({"request": {"user": user_member}}),
        )
        assert response_member.errors is None
        tasks_member = response_member.data["spaceById"]["tasks"]
        assert len(tasks_member) == 2

        # non member should only get the public task
        response_external = schema.execute_sync(
            space_by_id_query,
            context_value=BeneDict({"request": {"user": user_external}}),
        )

        assert response_external.errors is None
        tasks_external = response_external.data["spaceById"]["tasks"]
        assert len(tasks_external) == 1
        assert tasks_external[0].get("id") == str(public_task.id)

    def test_can_not_add_external_link_missing_required_fields(self):
        user = make_user()
        community = make_community(creator=user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        expectedErrors = [
            {
                "input": {"url": valid_url, "spaceId": valid_space_id, "type": valid_type},
                "expected_error": "was not provided",
            },
            {
                "input": {"url": valid_url, "type": valid_type, "name": valid_name},
                "expected_error": "was not provided",
            },
            {
                "input": {"spaceId": valid_space_id, "type": valid_type, "name": valid_name},
                "expected_error": "was not provided",
            },
            {
                "input": {"spaceId": valid_space_id, "url": valid_url, "name": valid_name},
                "expected_error": "was not provided",
            },
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                add_external_link_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": testCase["input"]},
            )

            assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addExternalLink"] if response.data else response.data) is None

    def test_validates_external_link_before_creation(self):
        user = make_user()
        community = make_community(creator=user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        expectedErrors = [
            {"field": "url", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "type", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "name", "value": None, "expected_error": "Expected non-nullable type"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                add_external_link_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert (
                    testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
                ), f"{str(response.errors[0].extensions)} does not contain code: {testCase['expected_code']} from testCase: {testCase}"
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["addExternalLink"] if response.data else response.data) is None

    def test_can_add_external_link(self):
        user = make_user()
        community = make_community(creator=user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                    url
                    type
                    name
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        response = schema.execute_sync(
            add_external_link_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": valid_input},
        )

        assert response.errors is None

        added_external_link = response.data["addExternalLink"]
        assert "id" in added_external_link
        assert valid_url == added_external_link["url"]
        assert valid_type in added_external_link["type"]
        assert valid_name == added_external_link["name"]

    def test_can_not_add_external_link_if_not_logged_in(self):
        community = make_community()
        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """
        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        response = schema.execute_sync(
            add_external_link_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def test_can_not_add_external_link_if_not_space_admin(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        add_external_link_mutation = """
            mutation test($input: AddExternalLinkInput!) {
                addExternalLink(input: $input) {
                    id
                }
            }
            """

        valid_space_id = str(community.id)
        valid_url = "https://www.instagram.com/"
        valid_type = "INSTAGRAM"
        valid_name = "Instagram"

        valid_input = {
            "spaceId": valid_space_id,
            "url": valid_url,
            "type": valid_type,
            "name": valid_name,
        }

        response = schema.execute_sync(
            add_external_link_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot add an external link to a community that you do not administrate"
            in response.errors[0].extensions["errors"]
        )

    def test_can_not_delete_external_link_if_not_logged_in(self):
        external_link = make_external_link()

        delete_external_link_mutation = """
            mutation test($id: UUID!) {
                deleteExternalLink(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_external_link_mutation,
            variable_values={"id": str(external_link.id)},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

    def test_can_not_delete_external_link_if_not_space_admin(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        external_link = make_external_link(community=community)

        delete_external_link_mutation = """
            mutation test($id: UUID!) {
                deleteExternalLink(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_external_link_mutation,
            variable_values={"id": str(external_link.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data is None
        assert (
            "You cannot delete an external link in a community that you do not administrate"
            in response.errors[0].extensions["errors"]
        )

    def test_can_delete_external_link_if_admin(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        delete_external_link_mutation = """
            mutation test($id: UUID!) {
                deleteExternalLink(id: $id) {
                    success
                }
            }
            """

        response = schema.execute_sync(
            delete_external_link_mutation,
            variable_values={"id": str(external_link.id)},
            context_value=BeneDict({"request": {"user": user}}),
        )

        assert response.data["deleteExternalLink"]["success"] is True
        assert response.errors is None

    def test_validates_external_link_before_update(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """
        base_input = {"id": str(external_link.id)}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"field": "id", "value": None, "expected_error": "Expected non-nullable type"},
            {
                "field": "id",
                "value": invalid_uuid,
                "expected_error": "No external link with the provided id exists.",
            },
            {"field": "url", "value": None, "expected_code": "null"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "holi.social", "expected_code": "invalid"},
            {"field": "type", "value": None, "expected_code": "null"},
            {"field": "name", "value": None, "expected_code": "null"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                update_external_link_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={
                    "input": base_input | {testCase["field"]: testCase["value"]},
                },
            )

            if "expected_code" in testCase:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert (
                    testCase["expected_code"] == field_errors[testCase["field"]][0]["code"]
                ), f"{str(response.errors[0].extensions)} does not contain code: {testCase['expected_code']} from testCase: {testCase}"
            else:
                assert testCase["expected_error"] in str(response.errors[0].message)
            assert (response.data["updateExternalLink"] if response.data else response.data) is None

    def test_can_not_update_external_link_without_passing_id(self):
        user = make_user()
        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        response = schema.execute_sync(
            update_external_link_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": {"url": "https://www.instagram.com/", "type": "INSTAGRAM"}},
        )

        assert response.data is None
        assert "Field 'id' of required type 'UUID!' was not provided" in response.errors[0].message

    def test_can_not_update_external_link_if_not_space_admin(self):
        user = make_user()

        community = make_community()
        community.add_member(user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        input = {
            "id": str(external_link.id),
            "url": "https://www.instagram.com/",
            "type": "INSTAGRAM",
            "name": "Instagram",
        }

        response = schema.execute_sync(
            update_external_link_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.data is None
        assert "You cannot update an external link in a community that you do not administrate" in str(
            response.errors[0].extensions["errors"]
        )

    def test_can_not_update_external_link_if_not_logged_in(self):
        external_link = make_external_link()

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        input = {
            "id": str(external_link.id),
            "url": "https://www.instagram.com/",
            "type": "INSTAGRAM",
            "name": "Instagram",
        }

        response = schema.execute_sync(
            update_external_link_mutation,
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
            variable_values={"input": input},
        )

        self.assert_is_unauthorized(response)

    def test_can_update_external_link(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                }
            }
            """

        input = {
            "id": str(external_link.id),
            "url": "https://www.instagram.com/",
            "type": "INSTAGRAM",
            "name": "Instagram",
        }

        response = schema.execute_sync(
            update_external_link_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert str(external_link.id) == response.data["updateExternalLink"]["id"]
        assert response.errors is None

    def test_updated_external_link_has_new_values(self):
        user = make_user()
        community = make_community(creator=user)

        external_link = make_external_link(community=community)

        update_external_link_mutation = """
            mutation test($input: UpdateExternalLinkInput!) {
                updateExternalLink(input: $input) {
                    id
                    url
                    type
                    name
                }
            }
            """
        id = str(external_link.id)
        new_url = "https://www.instagram.com/"
        new_type = "INSTAGRAM"
        new_name = "Instagram"

        input = {
            "id": id,
            "url": new_url,
            "type": new_type,
            "name": new_name,
        }

        response = schema.execute_sync(
            update_external_link_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        assert response.errors is None

        updated_external_link = response.data["updateExternalLink"]

        assert id == updated_external_link["id"]
        assert new_url == updated_external_link["url"]
        assert new_type == updated_external_link["type"]
        assert new_name == updated_external_link["name"]

    def test_check_app_version(self):
        app_version = AppVersion.objects.create(version="2023.5.1000", need_update=NeedUpdateType.MANDATORY)

        # Check success
        response = self.check_app_version(version="2023.5.1000", build_number="1000")
        assert response.errors is None
        assert response.data is not None
        assert response.data["checkAppVersion"]["needUpdate"] == app_version.need_update
        assert response.data["checkAppVersion"]["appStoreUrl"] == settings.APPLE_APP_STORE_DEFAULT_URL
        assert response.data["checkAppVersion"]["playStoreUrl"] == settings.GOOGLE_PLAY_STORE_DEFAULT_URL

        # Check error version not found
        response = self.check_app_version(version="2023.5.1234", build_number="1000")
        assert response.errors is None
        assert response.data is not None
        assert response.data["checkAppVersion"]["needUpdate"] == NeedUpdateType.NO

    def check_app_version(self, version: str, build_number: str):
        response = schema.execute_sync(
            f"""
            query {{
                checkAppVersion(version: "{version}", buildNumber: "{build_number}") {{
                    needUpdate
                    appStoreUrl
                    playStoreUrl
                }}
            }}
            """,
        )
        return response


def approve_verify_moderated_object(object_id, user):
    moderated_object = ModeratedObject.objects.filter(object_id=object_id).first()
    user.approve_moderated_object(moderated_object)
    user.verify_moderated_object(moderated_object)


def create_large_image_file():
    test_image = get_test_images()[-1]

    with open(test_image["path"], "rb") as file:
        content = file.read()
        return SimpleUploadedFile(name="image.jpg", content=content)


def create_video_file():
    test_video = get_test_videos()[0]

    with open(test_video["path"], "rb") as file:
        content = file.read()
        return SimpleUploadedFile(name="video.mp4", content=content)
