import copy
import json
import logging
import unittest
import uuid
from typing import List, Optional
from unittest import mock
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from benedict import BeneDict
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from requests.models import Response
from rest_framework import status

from openbook import settings
from openbook.graphql_schema import (
    ContentType,
    SpaceUserConnectionType,
    UpdateConnectionAction,
    schema,
)
from openbook.graphql_types import VisibilityFilter
from openbook_auth.models import User, UserConnectionStatus
from openbook_common.tests.helpers import (
    get_test_images,
    get_test_videos,
    make_authentication_headers_for_user,
    make_collaboration_tool,
    make_community,
    make_community_task,
    make_fake_post_text,
    make_fake_post_title,
    make_sdg,
    make_skill,
    make_topic,
    make_user,
    simple_jpeg_bytes,
)
from openbook_communities.models import Community, CommunityNotificationsSubscription
from openbook_common.types import VisibilityType
from openbook_insights.models import Insight
from openbook_moderation.models import ModeratedObject
from openbook_posts.models import PostCommentReaction

logger = logging.getLogger(__name__)


class GraphQLTest(TestCase):

    fixtures = ["openbook_circles/fixtures/circles.json", "openbook_moderation/fixtures/moderation_categories.json"]

    def test_get_authenticated_user_returns_self_reference(self):
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
        response = self.client.post(
            path=endpoint,
            data=json.dumps({"query": graphql_query}),
            content_type="application/json",
            **headers,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        authenticated_user = json.loads(response.content)["data"]["authenticatedUser"]
        self.assertEqual(authenticated_user["id"], str(user.uuid))
        self.assertEqual(authenticated_user["fullName"], user.profile.full_name())
        self.assertEqual(authenticated_user["engagementLevel"], user.profile.engagement_level)

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
        make_user(name="Thomas", last_name="Petersen"),
        make_user(name="Peter", last_name="Muster"),
        make_user(name="Petra", last_name="Meier"),
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
        self.assertEqual(executed.data["userByName"]["totalResults"], 3)
        self.assertEqual(executed.data["userByName"]["data"][0]["firstName"], "Peter")
        self.assertEqual(executed.data["userByName"]["data"][1]["firstName"], "Petra")
        self.assertEqual(executed.data["userByName"]["data"][2]["firstName"], "Thomas")

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
        geolocation = {"latitude": 2.0, "longitude": -4.2}
        self.assertNotEqual(User.objects.get(username=user.username).profile.pronouns, pronouns)
        first_name = "Peter"
        last_name = "Shaw"

        json_body = [
            {"op": "replace", "path": "/traits/given_name", "value": f"{first_name}"},
            {"op": "replace", "path": "/traits/family_name", "value": f"{last_name}"},
            {"op": "replace", "path": "/traits/name", "value": f"{first_name} {last_name}"},
        ]

        executed = schema.execute_sync(
            """
            mutation test($input: UpdateAuthenticatedUserInput!) {
                updateAuthenticatedUser(input: $input) {
                    id
                    pronouns
                    geolocation {
                        latitude
                        longitude
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={
                "input": {
                    "pronouns": pronouns,
                    "firstName": first_name,
                    "lastName": last_name,
                    "geolocation": geolocation,
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
        self.assertEqual(graphql_pronouns, persisted_profile.pronouns)
        self.assertEqual(graphql_pronouns, pronouns)
        self.assertEqual(last_name, persisted_profile.last_name)
        self.assertEqual(first_name, persisted_profile.name)
        self.assertIsNotNone(persisted_profile.geolocation)
        self.assertEqual(geolocation["longitude"], persisted_profile.geolocation.x)
        self.assertEqual(geolocation["latitude"], persisted_profile.geolocation.y)

        mock_publish_user_name_updated_event.assert_called_once_with(user=user)

    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("openbook.graphql_schema.publish_user_name_updated_event")
    def test_can_not_publish_user_name_updated_event_if_user_not_space_member(
        self, mock_publish_user_name_updated_event, mock_patch
    ):
        response = Response()
        response.status_code = 200
        response._content = str.encode(json.dumps({}))
        mock_patch.return_value = response
        user = make_user(name="Fritz", last_name="Meier")
        pronouns = "She/her"
        geolocation = {"latitude": 2.0, "longitude": -4.2}
        self.assertNotEqual(User.objects.get(username=user.username).profile.pronouns, pronouns)
        first_name = "Peter"
        last_name = "Shaw"

        schema.execute_sync(
            """
            mutation test($input: UpdateAuthenticatedUserInput!) {
                updateAuthenticatedUser(input: $input) {
                    id
                    pronouns
                    geolocation {
                        latitude
                        longitude
                    }
                }
            }
            """,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={
                "input": {
                    "pronouns": pronouns,
                    "firstName": first_name,
                    "lastName": last_name,
                    "geolocation": geolocation,
                }
            },
        )

        mock_publish_user_name_updated_event.assert_not_called()

    def test_can_perform_connection_workflow(self):
        first_user = make_user(name="Fritz", last_name="Meier")
        second_user = make_user(name="Gesine", last_name="Schinder")

        self.assertFalse(first_user.is_connected_with_user(second_user))

        connection_request_response = self.connect_to_user(first_user, second_user)

        self.assertEqual(
            connection_request_response.data["updateConnectionWithUser"]["id"],
            second_user.username,
        )

        self.assertTrue(second_user.is_pending_confirm_connection_for_user_with_id(first_user.pk))
        self.assertEqual(
            first_user.get_connection_status_with_user_id(second_user.pk),
            UserConnectionStatus.REQUESTED,
        )

        connection_confirm_response = self.connect_to_user(second_user, first_user)

        self.assertEqual(
            connection_confirm_response.data["updateConnectionWithUser"]["id"],
            first_user.username,
        )
        self.assertTrue(first_user.is_fully_connected_with_user_with_id(second_user.pk))
        self.assertTrue(second_user.is_fully_connected_with_user_with_id(first_user.pk))

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

        self.assertEqual(post_data["text"], post_text)
        self.assertEqual(post_data["title"], post_title)
        self.assertIsNone(post_data["image"])
        self.assertEqual(post_data["creator"]["id"], str(posting_user.uuid))
        self.assertIsNotNone(post_data["created"])
        self.assertEqual(post_data["numberOfComments"], 3)
        self.assertEqual(post_data["involvedUsers"]["totalResults"], 2)
        self.assertEqual(len(post_data["comments"]), 3)
        self.assertEqual(post_data["comments"][0]["text"], f"comment text 1 @{posting_user.username}")
        self.assertEqual(post_data["commenters"]["totalResults"], 1)
        self.assertEqual(post_data["commenters"]["data"][0]["firstName"], other_user.name)

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

        self.assertEqual(post_data["text"], post_text)
        self.assertEqual(post_data["title"], post_title)
        self.assertIn(image_name, post_data["image"]["url"])
        self.assertEqual(post_data["image"]["width"], 1)
        self.assertEqual(post_data["image"]["height"], 1)
        self.assertEqual(post_data["creator"]["id"], str(posting_user.uuid))
        self.assertIsNotNone(post_data["created"])

    def test_cant_fetch_post_draft(self):
        posting_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(text=post_text, title=post_title, is_draft=True)

        response = self.get_post_with_id_raw(post)

        post_data = response.data["postById"]
        self.assertEqual(post_data, None)
        self.assertIn("Post not found", response.errors[0].message)

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

        self.assertEqual(post.comments.count(), 2)
        response = self.delete_post_comment(comment.id, comment_user)
        self.assertIsNone(response.errors)
        self.assertEqual(response.data["deletePostComment"]["success"], True)
        self.assertEqual(post.comments.count(), 1)
        self.assertNotIn(comment.id, post.comments.values_list("id", flat=True))
        self.assertNotIn(
            reaction.id, PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)
        )

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

        self.assertEqual(post.comments.count(), 2)
        response = self.delete_post_comment(comment.id, other_user)
        self.assertIsNone(response.data, None)

        self.assertEqual(post.comments.count(), 2)
        self.assertIn(comment.id, post.comments.values_list("id", flat=True))
        self.assertIn(
            reaction.id, PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)
        )

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

        self.assertEqual(post.comments.count(), 2)
        response = self.delete_post_comment("00000000-0000-0000-0000-000000000000", comment_user)
        self.assertIsNone(response.data, None)

        self.assertEqual(post.comments.count(), 2)
        self.assertIn(comment.id, post.comments.values_list("id", flat=True))
        self.assertIn(
            reaction.id, PostCommentReaction.objects.filter(post_comment=comment).values_list("id", flat=True)
        )

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

        self.assertEqual(updated_post["myReaction"]["HEART"], 1)
        self.assertEqual(updated_post["reactions"]["HEART"], 1)

        post_data = self.get_post_with_id_data(post, other_user)
        self.assertEqual(post_data["myReaction"]["HEART"], 0)
        self.assertEqual(post_data["reactions"]["HEART"], 1)

        self.react_to_post(post, "REMOVE", posting_user)
        executed = self.react_to_post(post, "REMOVE", posting_user)  # setting twice is same as setting once
        updated_post = executed.data["updatePostReaction"]
        self.assertEqual(updated_post["myReaction"]["HEART"], 0)
        self.assertEqual(updated_post["reactions"]["HEART"], 0)

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

        self.assertEqual(updated_post_comment["myReaction"]["HEART"], 1)
        self.assertEqual(updated_post_comment["reactions"]["HEART"], 1)

        post_data = self.get_post_with_id_data(post, other_user)
        self.assertEqual(post_data["myReaction"]["HEART"], 0)
        self.assertEqual(post_data["reactions"]["HEART"], 0)
        self.assertEqual(post_data["comments"][0]["myReaction"]["HEART"], 0)
        self.assertEqual(post_data["comments"][0]["reactions"]["HEART"], 1)

        self.react_to_post_comment(comment, "REMOVE", posting_user)
        executed = self.react_to_post_comment(comment, "REMOVE", posting_user)  # setting twice is same as setting once
        updated_post_comment = executed.data["updatePostCommentReaction"]
        self.assertEqual(updated_post_comment["myReaction"]["HEART"], 0)
        self.assertEqual(updated_post_comment["reactions"]["HEART"], 0)

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

        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], 1)
        self.assertEqual(posts_data[0]["text"], input_data["text"])
        self.assertEqual(posts_data[0]["isPublic"], True)

        # space admin can create private post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(space_admin, input_data)

        data = response.data["createSpacePost"]
        posts_data = data["posts"]["data"]

        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], 2)
        self.assertEqual(posts_data[0]["text"], input_data["text"])
        self.assertEqual(posts_data[0]["isPublic"], False)

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

        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], 1)
        self.assertEqual(posts_data[0]["text"], input_data["text"])
        self.assertEqual(posts_data[0]["isPublic"], False)

        # member user cannot create public post
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(member_user, input_data)

        self.assertIsNotNone(response.errors)
        self.assertIsNone(response.data)
        self.assertIn(
            "You cannot add a public post to a community you're not administrator of", response.errors[0].message
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

        self.assertIsNotNone(response.errors)
        self.assertIsNone(response.data)
        self.assertIn("You cannot post to a community you're not member of", response.errors[0].message)

    def test_cant_create_space_post_invalid_input(self):
        space_admin = make_user()
        space = make_community(creator=space_admin)

        # test space id field is missing
        input_data = {
            "visibility": VisibilityType.MEMBERS.value,
            "text": make_fake_post_text(),
        }

        response = self.create_space_post(space_admin, input_data)
        self.assertIsNotNone(response.errors)
        self.assertIsNone(response.data)
        self.assertIn("Field 'spaceId' of required type 'UUID!' was not provided", response.errors[0].message)

        # test post text field is missing
        input_data = {
            "spaceId": str(space.id),
            "visibility": VisibilityType.PUBLIC.value,
        }

        response = self.create_space_post(space_admin, input_data)
        self.assertIsNotNone(response.errors)
        self.assertIsNone(response.data)
        self.assertIn("Field 'text' of required type 'String!' was not provided", response.errors[0].message)

        # test visibility field is missing
        input_data = {"spaceId": str(space.id), "text": make_fake_post_text()}

        response = self.create_space_post(space_admin, input_data)
        self.assertIsNotNone(response.errors)
        self.assertIsNone(response.data)
        self.assertIn(
            "Field 'visibility' of required type 'VisibilityType!' was not provided", response.errors[0].message
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

        self.assertIsNone(response.errors)
        insights = response.data["insightsByUserId"]["data"]
        self.assertEqual(2, len(insights))

        insight1_result = insights[0]
        self.assertEqual(insight1_result["title"], insight1.title)
        self.assertEqual(insight1_result["headerImage"], insight1.header_image)

        insight2_result = insights[1]
        self.assertEqual(insight2_result["title"], insight2.title)

        self.assertNotIn(insight3.title, [insight["title"] for insight in insights])

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

        self.assertIsNone(response.errors)
        insights = response.data["insightsByUserId"]["data"]
        self.assertEqual(2, len(insights))

        insight1_result = insights[0]
        self.assertEqual(insight1_result["title"], insight1.title)
        self.assertEqual(insight1_result["headerImage"], insight1.header_image)

        insight2_result = insights[1]
        self.assertEqual(insight2_result["title"], insight2.title)

        self.assertNotIn(insight3.title, [insight["title"] for insight in insights])

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

        self.assertIsNone(response.data)
        self.assertEqual(1, len(response.errors))
        self.assertEqual("User not found", str(response.errors[0].message))

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
        self.assertEqual(4, len(insights))
        # insight1 = next(i for i in insights if i["title"] == insight1_title)
        # insight2 = next(i for i in insights if i["title"] == insight2_title)
        insight1_result = insights[0]
        self.assertEqual(insight1_result["title"], insight1.title)
        self.assertEqual(insight1_result["numberOfPosts"], 2)
        self.assertEqual(insight1_result["posts"][0]["title"], post_title_public)
        self.assertEqual(insight1_result["posts"][1]["title"], post_title_public)
        self.assertEqual(insight1_result["involvedUsers"]["totalResults"], 2)

        insight2_result = insights[1]
        self.assertEqual(insight2_result["title"], insight3.title)
        self.assertEqual(insight2_result["numberOfPosts"], 1)
        self.assertEqual(insight2_result["involvedUsers"]["totalResults"], 1)

        insight3_result = insights[2]
        self.assertEqual(insight3_result["title"], insight2.title)
        self.assertEqual(insight3_result["numberOfPosts"], 1)
        self.assertEqual(insight3_result["involvedUsers"]["totalResults"], 2)

        insight4_result = insights[3]
        self.assertEqual(insight4_result["title"], insight4.title)
        self.assertEqual(insight4_result["numberOfPosts"], 0)
        self.assertEqual(insight4_result["involvedUsers"]["totalResults"], 1)

    def test_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")

        self.connect_to_user(following_user, followed_user)

        response = self.get_notifications(followed_user)
        self.assertGreaterEqual(response["totalResults"], 1)
        notifications = response["data"]
        connection_requested_notification = next(n for n in notifications if n["notificationType"] == "CR")
        self.assertEqual(
            connection_requested_notification["owner"]["fullName"],
            followed_user.profile.full_name(),
        )
        self.assertEqual(
            connection_requested_notification["options"]["user"]["fullName"],
            following_user.profile.full_name(),
        )

        self.connect_to_user(followed_user, following_user)

        notifications = self.get_notifications(followed_user)["data"]
        connection_accepted_notification = next(n for n in notifications if n["notificationType"] == "CA")
        self.assertEqual(
            connection_accepted_notification["options"]["user"]["fullName"],
            following_user.profile.full_name(),
        )

        notifications = self.get_notifications(following_user)["data"]
        connection_confirmed_notification = next(n for n in notifications if n["notificationType"] == "CC")
        self.assertEqual(
            connection_confirmed_notification["options"]["user"]["fullName"],
            followed_user.profile.full_name(),
        )

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
        self.assertEqual(response["totalResults"], 1)

        notification = response["data"][0]
        self.assertEqual(notification["options"]["post"]["title"], post1.title)
        self.assertEqual(notification["options"]["teaser"], post1.title)

        post2 = post_user.create_community_encircled_post(
            text=make_fake_post_text(),
            space_id=space.id,
            visibility=VisibilityType.MEMBERS.value,
        )

        response = self.get_notifications(subscriber_user)
        self.assertEqual(response["totalResults"], 2)

        notification = response["data"][0]
        self.assertIsNone(notification["options"]["post"]["title"])
        expected_teaser = " ".join(post2.text.split()[:3]) + "..."
        self.assertEqual(notification["options"]["teaser"], expected_teaser)

    def test_has_new_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")
        following_user2 = make_user(name="Other2")

        self.assertFalse(self.has_new_notifications(followed_user)["status"])

        self.connect_to_user(following_user, followed_user)
        self.assertTrue(self.has_new_notifications(followed_user)["status"])

        self.disconnect_from_user(following_user, followed_user)
        self.assertFalse(self.has_new_notifications(followed_user)["status"])

        self.connect_to_user(following_user, followed_user)
        self.assertTrue(self.has_new_notifications(followed_user)["status"])

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
        self.assertFalse(response.data["lastSeenNotification"]["status"])
        self.assertFalse(self.has_new_notifications(followed_user)["status"])

        self.connect_to_user(following_user2, followed_user)
        self.assertTrue(self.has_new_notifications(followed_user)["status"])

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
        self.assertIsNone(response.errors)
        data = response.data["hasNewNotifications"]
        return data

    def disconnect_from_user(self, following_user, followed_user):
        return self.connect_user(following_user, followed_user, UpdateConnectionAction.DISCONNECT)

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
        self.assertIsNone(connection_request_response.errors)
        return connection_request_response

    def test_filters_for_spaces(self):
        creator = make_user()
        topic1 = make_topic()
        topic2 = make_topic()
        space1 = make_community(creator=creator, topics=[topic1, topic2], location="Location1")
        space2 = make_community(topics=[topic1], location="Location2")
        skill1 = make_skill()
        skill2 = make_skill()
        skill3 = make_skill()
        make_community_task(space1, skills=[skill1, skill2])
        make_community_task(space2, skills=[skill2, skill3])

        filter_query = """
            query($topicId: UUID, $location: String, $skillIds: [UUID], $memberId: UUID) {
                spaces(topicId: $topicId, location: $location, skillIds: $skillIds, memberId: $memberId) {
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
        assert_filtered_spaces({}, [space1, space2])

        # Filter by common topic
        assert_filtered_spaces({"topicId": str(topic1.id)}, [space1, space2])

        # Filter by unique topic
        assert_filtered_spaces({"topicId": str(topic2.id)}, [space1])

        # Filter by location
        assert_filtered_spaces({"location": space2.location}, [space2])

        # Filter by topic and location
        assert_filtered_spaces({"topicId": str(topic1.id), "location": space1.location}, [space1])

        # Filter by single skill
        assert_filtered_spaces({"skillIds": [str(skill1.id)]}, [space1])

        # Filter by multiple skills
        assert_filtered_spaces({"skillIds": [str(skill1.id), str(skill3.id)]}, [space1, space2])

        # Filter by skills and location
        assert_filtered_spaces({"skillIds": [str(skill2.id)], "location": space2.location}, [space2])

        # Filter by skills and topics
        assert_filtered_spaces({"skillIds": [str(skill2.id)], "topicId": str(topic2.id)}, [space1])

        assert_filtered_spaces({"memberId": creator.username}, [space1])
        assert_filtered_spaces({"memberId": creator.username, "location": space1.location}, [space1])
        assert_filtered_spaces({"memberId": creator.username, "location": space2.location}, [])

        # Filter by skills, topics and location
        assert_filtered_spaces(
            {
                "skillIds": [str(skill3.id)],
                "location": space1.location,
                "topicId": str(topic2.id),
            },
            [],
        )

    def test_filters_for_discover_spaces(self):
        topic1 = make_topic()
        topic2 = make_topic()
        space1 = make_community(topics=[topic1, topic2], location="Location1")
        space2 = make_community(topics=[topic1], location="Location2")
        space3 = make_community(topics=[topic2], location="Location2")
        skill1 = make_skill()
        skill2 = make_skill()
        skill3 = make_skill()
        make_community_task(space1, skills=[skill1, skill2])
        make_community_task(space2, skills=[skill2, skill3])

        filter_query = """
            query($topicIds: [UUID], $location: String, $skillIds: [UUID]) {
                discoverSpaces(topicIds: $topicIds, location: $location, skillIds: $skillIds) {
                    topicId
                    skillId
                    location
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
            filter_response = schema.execute_sync(filter_query, variable_values=filter_options)
            expected_data = list(map(transform_space, expected_spaces))
            self.assert_paged_results_equal(
                filter_response.data["discoverSpaces"][0]["spaces"],
                expected_data,
            )

        # Filter by common topic
        assert_filtered_spaces({"topicIds": [str(topic1.id)]}, [space1, space2])

        # Filter by unique topic
        assert_filtered_spaces({"topicIds": [str(topic2.id)]}, [space1, space3])

        # Filter by topic and location
        assert_filtered_spaces({"topicIds": [str(topic1.id)], "location": space1.location}, [space1])

        # Filter by skills and topics
        assert_filtered_spaces(
            {"skillIds": [str(skill2.id)], "topicIds": [str(topic2.id)]},
            [space1, space3],
        )

        # Filter by skills, topics and location
        assert_filtered_spaces(
            {
                "skillIds": [str(skill3.id)],
                "location": space1.location,
                "topicIds": [str(topic2.id)],
            },
            [space1],
        )

        filter_response = schema.execute_sync(
            filter_query, variable_values={"topicIds": [str(topic1.id), str(topic2.id)]}
        )
        self.assertEqual(len(filter_response.data["discoverSpaces"]), 2)
        t1, t2 = (0, 1) if filter_response.data["discoverSpaces"][0]["topicId"] == str(topic1.id) else (1, 0)

        self.assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t1]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        self.assert_paged_results_equal(
            filter_response.data["discoverSpaces"][t2]["spaces"],
            list(map(transform_space, [space1, space3])),
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

        self.assertEqual(len(response), 3)
        created_section = response[0]
        self.assertEqual(created_section["section"], "Created")
        self.assertEqual(created_section["type"], SpaceUserConnectionType.CREATOR.value)
        self.assertEqual(created_section["spaces"]["totalResults"], 1)
        self.assertEqual(created_section["spaces"]["data"][0]["id"], str(space1.id))
        joined_section = response[1]
        self.assertEqual(joined_section["section"], "Joined")
        self.assertEqual(joined_section["type"], SpaceUserConnectionType.MEMBER.value)
        self.assertEqual(joined_section["spaces"]["totalResults"], 1)
        self.assertEqual(joined_section["spaces"]["data"][0]["id"], str(space2.id))
        following_section = response[2]
        self.assertEqual(following_section["section"], "Following")
        self.assertEqual(following_section["type"], SpaceUserConnectionType.FOLLOWER.value)
        self.assertEqual(following_section["spaces"]["totalResults"], 1)
        self.assertEqual(following_section["spaces"]["data"][0]["id"], str(space4.id))

    @mock.patch("openbook.graphql_schema.publish_space_user_added_event")
    def test_space_membership_request_approval_process(self, mock_publish_space_user_added_event):
        membership_requestor = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)
        mock_publish_space_user_added_event.retrun_value = None

        def member_result(user, is_admin):
            return {
                "user": {"id": user.username},
                "isAdministrator": is_admin,
            }

        # Preconditions
        pre_join_space = self.get_space_for_user(membership_requestor, space)
        self.assertEqual(pre_join_space["connectionStatusToMyself"], [])
        self.assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = self.get_notifications(membership_requestor)
        self.assertEqual(data["totalResults"], 0)
        data = self.get_notifications(space_creator)
        self.assertEqual(data["totalResults"], 0)

        # Send Join Request
        after_request_space = self.mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        self.assertCountEqual(
            after_request_space["connectionStatusToMyself"],
            [SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value, SpaceUserConnectionType.FOLLOWER.value],
        )

        # Staff received MembershipRequest notification
        staff_request_received_notification = self.get_notifications(space_creator)["data"][0]
        self.assertEqual(staff_request_received_notification["notificationType"], "CMR")
        self.assertEqual(staff_request_received_notification["options"]["space"]["title"], space.title)
        self.assertEqual(
            staff_request_received_notification["options"]["user"]["fullName"],
            membership_requestor.profile.full_name(),
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
        self.assertCountEqual(
            self.get_space_for_user(membership_requestor, space)["connectionStatusToMyself"],
            [SpaceUserConnectionType.MEMBER.value, SpaceUserConnectionType.FOLLOWER.value],
        )

        # User has approval notification
        membership_requestor_notifications = self.get_notifications(membership_requestor)
        self.assertEqual(membership_requestor_notifications["totalResults"], 1)
        self.assertEqual(membership_requestor_notifications["data"][0]["notificationType"], "CMRA")

        # Staff has approval notification
        staff_notifications = self.get_notifications(space_creator)
        self.assertEqual(staff_notifications["totalResults"], 1)
        self.assertEqual(staff_notifications["data"][0]["notificationType"], "CMRA")
        self.assertEqual(staff_notifications["data"][0]["options"]["space"]["title"], space.title)
        self.assertEqual(
            staff_notifications["data"][0]["options"]["user"]["fullName"],
            membership_requestor.profile.full_name(),
        )

    @mock.patch("openbook.graphql_schema.publish_space_user_added_event")
    def test_space_membership_request_rejection_process(self, mock_publish_space_user_added_event):
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
        self.assertEqual(pre_join_space["connectionStatusToMyself"], [])
        self.assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator, is_admin=True)])

        data = self.get_notifications(membership_requestor)
        self.assertEqual(data["totalResults"], 0)
        data = self.get_notifications(space_creator)
        self.assertEqual(data["totalResults"], 0)

        # Send Join Request
        after_request_space = self.mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        self.assertCountEqual(
            after_request_space["connectionStatusToMyself"],
            [SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value, SpaceUserConnectionType.FOLLOWER.value],
        )

        # Staff received MembershipRequest notification
        staff_request_received_notification = self.get_notifications(space_creator)["data"][0]
        self.assertEqual(staff_request_received_notification["notificationType"], "CMR")
        self.assertEqual(staff_request_received_notification["options"]["space"]["title"], space.title)
        self.assertEqual(
            staff_request_received_notification["options"]["user"]["fullName"],
            membership_requestor.profile.full_name(),
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
        self.assertCountEqual(
            self.get_space_for_user(membership_requestor, space)["connectionStatusToMyself"],
            [SpaceUserConnectionType.FOLLOWER.value],
        )

        # User has no notification
        membership_requestor_notifications = self.get_notifications(membership_requestor)
        self.assertEqual(membership_requestor_notifications["totalResults"], 0)

        # Staff has no notification
        staff_notifications = self.get_notifications(space_creator)
        self.assertEqual(staff_notifications["totalResults"], 0)

        mock_publish_space_user_added_event.assert_not_called()

    def test_space_admin_grant_and_revoke_admin_access_success(self):
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

    def test_space_admin_grant_and_revoke_admin_access_errors(self):
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

        self.assertIsNone(response.data)
        self.assertIsNotNone(response.errors)
        self.assertIn("User is already an administrator.", response.errors[0].message)
        self.assertTrue(
            space.is_user_with_username_administrator_of_community_with_name(space_admin.username, space.name)
        )

        # Admin user cannot grant admin privileges to an external user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.GRANT_ADMIN_ACCESS,
            user_id=external_user.username,
        )

        self.assertIsNone(response.data)
        self.assertIsNotNone(response.errors)
        self.assertIn("Cannot make administrator a user that is not part of the space.", response.errors[0].message)
        self.assertFalse(space.is_user_with_username_member_of_community_with_name(external_user.username, space.name))

        # Admin user cannot revoke admin privileges to a member user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=space_admin,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_member.username,
        )

        self.assertIsNone(response.data)
        self.assertIsNotNone(response.errors)
        self.assertIn("User to remove is not an administrator.", response.errors[0].message)
        self.assertFalse(
            space.is_user_with_username_administrator_of_community_with_name(space_member.username, space.name)
        )

    def test_space_member_grant_and_revoke_admin_access_errors(self):
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

        self.assertIsNone(response.data)
        self.assertIn(
            "Only the administrators of the space can grant administrator privileges.", response.errors[0].message
        )
        self.assertFalse(
            space.is_user_with_username_administrator_of_community_with_name(member_user_2.username, space.name)
        )

        # Member user cannot revoke admin privileges to an admin user
        response = self.mutate_update_space_user_connection_raw(
            auth_user=member_user,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.ADMINISTRATOR,
            connect_action=UpdateConnectionAction.REVOKE_ADMIN_ACCESS,
            user_id=space_creator.username,
        )

        self.assertIsNone(response.data)
        self.assertIn(
            "Only the administrators of the space can revoke administrator privileges.", response.errors[0].message
        )
        self.assertFalse(
            space.is_user_with_username_administrator_of_community_with_name(member_user_2.username, space.name)
        )

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
        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], len(public_posts) + len(private_posts))
        self.assertCountEqual(self.private_post_ids(posts_data), private_ids)
        self.assertCountEqual(self.public_post_ids(posts_data), public_ids)
        self.assertGreaterEqual(posts_data[0]["created"], posts_data[1]["created"])

        # member user with visibility public posts shows only public posts
        data = self.get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.PUBLIC)
        posts_data = data["posts"]["data"]
        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], len(public_posts))
        self.assertCountEqual(self.public_post_ids(posts_data), public_ids)
        self.assertCountEqual(self.private_post_ids(posts_data), [])
        self.assertGreaterEqual(posts_data[0]["created"], posts_data[1]["created"])

        # member user with visibility private posts shows only private posts
        data = self.get_space_by_id_with_posts(user_member, space.id, VisibilityFilter.MEMBERS)
        posts_data = data["posts"]["data"]
        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], len(private_posts))
        self.assertCountEqual(self.public_post_ids(posts_data), [])
        self.assertCountEqual(self.private_post_ids(posts_data), private_ids)
        self.assertGreaterEqual(posts_data[0]["created"], posts_data[1]["created"])

        # external user without visibility filter shows public posts
        data = self.get_space_by_id_with_posts(user_external, space.id)
        posts_data = data["posts"]["data"]
        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], len(public_posts))
        self.assertCountEqual(self.public_post_ids(posts_data), public_ids)
        self.assertCountEqual(self.private_post_ids(posts_data), [])
        self.assertGreaterEqual(posts_data[0]["created"], posts_data[1]["created"])

        # external user visibility filter is ignored and shows public posts
        data = self.get_space_by_id_with_posts(user_external, space.id, VisibilityFilter.MEMBERS)
        posts_data = data["posts"]["data"]
        self.assertEqual(data["id"], str(space.id))
        self.assertEqual(data["posts"]["totalResults"], len(public_posts))
        self.assertCountEqual(self.public_post_ids(posts_data), public_ids)
        self.assertCountEqual(self.private_post_ids(posts_data), [])
        self.assertGreaterEqual(posts_data[0]["created"], posts_data[1]["created"])

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

        self.assertIsNone(response.errors)
        self.assertEqual(response.data["reportContent"]["success"], True)

        self.assertEqual(reporting_user.can_see_post(post), True)
        self.assertEqual(other_user.can_see_post(post), True)

        post_data = self.get_post_with_id_data(post, reporting_user)
        self.assertEqual(post_data["id"], str(post.id))

        post_data = self.get_post_with_id_data(post, other_user)
        self.assertEqual(post_data["id"], str(post.id))

        approve_verify_moderated_object(post.id, posting_user)

        response = self.get_post_with_id_raw(post, other_user)
        self.assertFalse(other_user.can_see_post(post))
        self.assertIsNone(response.data["postById"])

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

        self.assertIsNone(response.errors)
        self.assertEqual(response.data["reportContent"]["success"], True)

        post_data = self.get_post_with_id_data(post, reporting_user)
        self.assertEqual(len(post_data["comments"]), 1)

        approve_verify_moderated_object(comment.id, posting_user)

        post_data = self.get_post_with_id_data(post, other_user)
        self.assertEqual(len(post_data["comments"]), 0)

    @unittest.skip("Fundamentally broken on Postgres, even though this test would work")
    def test_report_user(self):
        user = make_user()
        user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        user_before_report = self.get_user_with_id_data(user, reporting_user)
        self.assertEqual(user_before_report["id"], user.username)

        user_before_report = self.get_user_with_id_data(user)
        self.assertEqual(user_before_report["id"], user.username)

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

        self.assertIsNone(response.errors)
        self.assertEqual(response.data["reportContent"]["success"], True)

        response = self.get_user_with_id_raw(user, reporting_user)
        self.assertIsNone(response.data)

        user_before_approve = self.get_user_with_id_data(user, other_user)
        self.assertEqual(user_before_approve["id"], user.username)
        user_before_approve = self.get_user_with_id_data(user)
        self.assertEqual(user_before_approve["id"], user.username)

        approve_verify_moderated_object(user.id, user)

        response_after_approve = self.get_user_with_id_raw(user, other_user)
        self.assertIsNone(response_after_approve.data["userById"])
        response_after_approve = self.get_user_with_id_raw(user)
        self.assertIsNone(response_after_approve.data["userById"])

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

        self.assertIsNone(response.errors)
        self.assertEqual(response.data["reportContent"]["success"], True)

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
        self.assertIsNone(response.errors)
        self.assertEqual(len(response.data["spaceById"]), 1)
        self.assertEqual(response.data["spaceById"]["id"], str(space.id))

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
        self.assertIsNone(response.errors)
        self.assertEqual(len(response.data["spaceById"]), 1)
        self.assertEqual(response.data["spaceById"]["name"], str(space.name))

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
        self.assertIsNone(response.data["spaceById"])

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
        self.assertEqual(response.data["userSuggestions"]["totalResults"], 2)

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
        self.assertIsNone(blocked_post_raw.data["postById"])
        other_post_data = self.get_post_with_id_data(other_post, blocking_user)
        self.assertEqual(other_post_data["involvedUsers"]["totalResults"], 1)
        self.assertEqual(other_post_data["numberOfComments"], 0)
        self.assertEqual(other_post_data["commenters"]["totalResults"], 0)

        self.assertIsNone(response.errors)
        self.assertEqual(response.data["blockUser"]["success"], True)

        response_after_blocking = self.get_user_with_id_raw(blocked_user, blocking_user)
        self.assertIsNone(response_after_blocking.data["userById"])

        response_after_blocking = self.get_user_with_id_raw(blocking_user, blocked_user)
        self.assertIsNone(response_after_blocking.data["userById"])

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
        self.assertEqual(response.data["userSuggestions"]["totalResults"], 1)
        self.assertEqual(response.data["userSuggestions"]["data"][0]["fullName"], "OtherUser")

    # Utility methods

    def get_user_with_id_data(self, user_to_get, calling_user=None):
        response = self.get_user_with_id_raw(user_to_get, calling_user)
        self.assertIsNone(response.errors)
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
        self.assertIsNone(response.errors)
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
        self.assertIsNone(response.errors)
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

        self.assertIsNone(response.errors)
        return response.data["spaceById"]

    def get_space_by_id_with_posts(self, user: User, id: uuid, visibility: VisibilityFilter = VisibilityFilter.ALL):
        response = schema.execute_sync(
            """
            query($id:String!, $visibility:VisibilityFilter!) {
                spaceById(idOrName:$id) {
                    id
                    name
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

        self.assertIsNone(response.errors)
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
        self.assertIsNone(response.errors)
        return response.data["notifications"]

    def assert_paged_results_equal(self, results: dict, expected_data: List[dict[str, any]]):
        self.assertEqual(results["totalResults"], len(expected_data))

        for el in expected_data:
            self.assertIn(el, results["data"])

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

        self.assertEqual("required", response.errors[0].original_error.detail["title"][0].code)
        self.assertEqual("required", response.errors[0].original_error.detail["description"][0].code)
        self.assertIsNone(response.data)

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

            self.assertIsNotNone(response.errors, testCase)
            if "expected_code" in testCase:
                self.assertIn(
                    testCase["expected_code"],
                    str(response.errors[0].message),
                    f"{str(response.errors[0].message)} does not contain code: {testCase['expected_code']} from testCase: {testCase}",
                )
            else:
                self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data)

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

            self.assertTrue(response.data["validateSpace"]["success"])
            self.assertIsNone(response.errors)

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
        self.assertIsNone(response.data)
        self.assertIn("Unauthorized", str(response.errors[0].message))
        self.assertEqual("UNAUTHORIZED", str(response.errors[0].extensions["code"]))

    @mock.patch("openbook.graphql_schema.publish_space_created_event")
    def test_can_not_create_spaces_missing_required_fields(self, mock_publish_space_created_event):
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

            self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data["createSpace"] if response.data else response.data)

        mock_publish_space_created_event.assert_not_called()

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
                self.assertIn(
                    testCase["expected_code"],
                    str(response.errors[0].message),
                    f"{str(response.errors[0].message)} does not contain code: {testCase['expected_code']} from testCase: {testCase}",
                )
            else:
                self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data["createSpace"] if response.data else response.data)

    @mock.patch("openbook.graphql_schema.publish_space_created_event")
    def test_can_create_space(self, mock_publish_space_created_event):
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

        self.assertIsNone(response.errors)

        created_space = response.data["createSpace"]
        self.assertIn("id", created_space)
        self.assertEqual("valid", created_space["name"])
        self.assertEqual("valid", created_space["title"])
        self.assertEqual("valid", created_space["description"])
        self.assertEqual(len(topic_ids), len(created_space["topics"]))
        for topic in created_space["topics"]:
            self.assertIn(topic["id"], topic_ids)
        self.assertIn("cover.jpg", created_space["cover"])

        # Verify that creator is admin
        self.assertEqual(1, len(created_space["members"]["data"]))
        member = created_space["members"]["data"][0]
        self.assertEqual(str(user.username), member["user"]["id"])
        self.assertTrue(member["isAdministrator"])

        community = Community.objects.get(id=created_space["id"])
        mock_publish_space_created_event.assert_called_once_with(community=community)

    @mock.patch("openbook.graphql_schema.publish_space_created_event")
    def test_can_not_create_space_if_not_logged_in(self, mock_publish_space_created_event):
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
            {"field": "id", "value": None, "expected_code": "null"},
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
            {"field": "contactMail", "value": "invalid", "expected_code": "invalid"},
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
                self.assertIn(
                    testCase["expected_code"],
                    str(response.errors[0].message),
                    f"{str(response.errors[0].message)} does not contain code: {testCase['expected_code']} from testCase: {testCase}",
                )
            else:
                self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data["updateSpace"] if response.data else response.data)

    def test_can_not_update_space_without_passing_id(self):
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

        self.assertIsNone(response.data)
        self.assertIn("Field 'id' of required type 'UUID!' was not provided", response.errors[0].message)

    def test_can_update_space(self):
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
        ]

        for input in valid_inputs:
            response = schema.execute_sync(
                update_space_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": base_input | input},
            )

            self.assertEqual(str(community.id), response.data["updateSpace"]["id"])
            self.assertIsNone(response.errors)

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

        self.assertIsNone(response.errors)

        updated_space = response.data["updateSpace"]
        self.assertEqual(str(community.id), updated_space["id"])
        self.assertEqual("newest title", updated_space["title"])
        self.assertEqual("newest description", updated_space["description"])
        self.assertEqual(len(topic_ids), len(updated_space["topics"]))
        for topic in updated_space["topics"]:
            self.assertIn(topic["id"], topic_ids)
        self.assertIn("cover.jpg", updated_space["cover"])
        self.assertIn("avatar.jpg", updated_space["avatar"])
        self.assertEqual(len(sdg_ids), len(updated_space["sdgs"]))
        for sdg in updated_space["sdgs"]:
            self.assertIn(sdg["id"], sdg_ids)
        self.assertEqual("Hamburg, Germany", updated_space["location"])
        self.assertEqual("Lorem ipsum", updated_space["contactDescription"])
        self.assertEqual("+49 123 12345", updated_space["contactPhone"])
        self.assertEqual("contact@space.com", updated_space["contactEmail"])

    def test_can_not_update_space_if_not_admin(self):
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

        self.assertIsNone(response.data)
        self.assertIn("Can't update a community that you do not administrate.", str(response.errors[0].message))

    def test_can_not_update_space_if_not_logged_in(self):
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

    def test_can_not_delete_space_if_not_admin(self):
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

        self.assertIsNone(response.data)
        self.assertIn("Can't delete a community that you do not administrate.", str(response.errors[0].message))

    def test_can_not_delete_space_if_not_logged_in(self):
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

    def test_can_delete_space(self):
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

        self.assertTrue(response.data["deleteSpace"]["success"])
        self.assertIsNone(response.errors)

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
        valid_url = "https://project-holi.org/"
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

            self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data["addCollaborationTool"] if response.data else response.data)

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
        valid_url = "https://project-holi.org/"
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
            {"field": "url", "value": "project-holi.org", "expected_code": "invalid"},
            {"field": "title", "value": None, "expected_error": "Expected non-nullable type"},
            {"field": "title", "value": "", "expected_code": "blank"},
            {"field": "title", "value": "c", "expected_code": "min_length"},
            {"field": "title", "value": "c" * 61, "expected_code": "max_length"},
            {"field": "description", "value": "c", "expected_code": "min_length"},
            {"field": "description", "value": "c" * 101, "expected_code": "max_length"},
            {"field": "collectionType", "value": None, "expected_code": "Expected non-nullable type"},
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                add_collaboration_tool_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                self.assertIn(
                    testCase["expected_code"],
                    str(response.errors[0].message),
                    f"{str(response.errors[0].message)} does not contain code: {testCase['expected_code']} from testCase: {testCase}",
                )
            else:
                self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data["addCollaborationTool"] if response.data else response.data)

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
        valid_url = "https://project-holi.org/"
        valid_title = "Project Holi"
        valid_description = "holi is the network where people and organizations come together for the common good"
        valid_collection_type = "COLLABORATION"
        valid_domain = "Project-Holi"

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

        self.assertIsNone(response.errors)

        added_collaboration_tool = response.data["addCollaborationTool"]
        self.assertIn("id", added_collaboration_tool)
        self.assertEqual(valid_url, added_collaboration_tool["url"])
        self.assertEqual(valid_title, added_collaboration_tool["title"])
        self.assertEqual(valid_description, added_collaboration_tool["description"])
        self.assertIn(valid_collection_type, added_collaboration_tool["collectionType"])
        self.assertIn(valid_domain, added_collaboration_tool["domain"])

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
        valid_url = "https://project-holi.org/"
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
        valid_url = "https://project-holi.org/"
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

        self.assertIsNone(response.data)
        self.assertIn(
            "You cannot add a collaboration tool to a community you are not a member of", response.errors[0].message
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

        self.assertIsNone(response.data)
        self.assertIn(
            "You cannot delete a collaboration tool in a community you are not a member of", response.errors[0].message
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

        self.assertTrue(response.data["deleteCollaborationTool"]["success"])
        self.assertIsNone(response.errors)

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

        self.assertTrue(response.data["deleteCollaborationTool"]["success"])
        self.assertIsNone(response.errors)

    def test_validate_collaboration_tool_before_update(self):
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
            {"field": "id", "value": None, "expected_code": "null"},
            {
                "field": "id",
                "value": invalid_uuid,
                "expected_error": "No collaboration tool with the provided id exists",
            },
            {"field": "url", "value": None, "expected_code": "null"},
            {"field": "url", "value": "", "expected_code": "blank"},
            {"field": "url", "value": "project-holi.org", "expected_code": "invalid"},
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
                self.assertIn(
                    testCase["expected_code"],
                    str(response.errors[0].message),
                    f"{str(response.errors[0].message)} does not contain code: {testCase['expected_code']} from testCase: {testCase}",
                )
            else:
                self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data["updateSpace"] if response.data else response.data)

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
            variable_values={"input": {"url": "https://project-holi.org/"}},
        )

        self.assertIsNone(response.data)
        self.assertIn("Field 'id' of required type 'UUID!' was not provided", response.errors[0].message)

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

        input = {"id": str(collaboration_tool.id), "url": "https://project-holi.org/"}

        response = schema.execute_sync(
            update_collaboration_tool_mutation,
            context_value=BeneDict({"request": {"user": user}}),
            variable_values={"input": input},
        )

        self.assertIsNone(response.data)
        self.assertIn(
            "You cannot update a collaboration tool in a community you are not a member of",
            str(response.errors[0].message),
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

        input = {"id": str(collaboration_tool.id), "url": "https://project-holi.org/"}

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

        valid_url = "https://project-holi.org/"
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

            self.assertEqual(str(collaboration_tool.id), response.data["updateCollaborationTool"]["id"])
            self.assertIsNone(response.errors)

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
        new_url = "https://project-holi.org/"
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

        self.assertIsNone(response.errors)

        updated_collaboration_tool = response.data["updateCollaborationTool"]

        self.assertEqual(id, updated_collaboration_tool["id"])
        self.assertEqual(new_url, updated_collaboration_tool["url"])
        self.assertEqual(new_title, updated_collaboration_tool["title"])
        self.assertEqual(new_description, updated_collaboration_tool["description"])
        self.assertEqual(new_collection_type, updated_collaboration_tool["collectionType"])

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

            self.assertIn(expected_errors[input_key], str(response.errors[0].message))
            self.assertIsNone(response.data["createTask"] if response.data else response.data)

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
            {"field": "locationType", "value": None, "expected_code": "Expected non-nullable type"},
            {"field": "regularity", "value": None, "expected_code": "Expected non-nullable type"},
            {"field": "contactEmail", "value": None, "expected_code": "Expected non-nullable type"},
            {"field": "contactPhone", "value": "c" * 500, "expected_code": "max_length"},
            {
                "field": "skills",
                "value": [non_existent_skill_id],
                "expected_code": f"No skill with the id '{non_existent_skill_id}' found.",
            },
        ]

        for testCase in expectedErrors:
            response = schema.execute_sync(
                create_task_mutation,
                context_value=BeneDict({"request": {"user": user}}),
                variable_values={"input": valid_input | {testCase["field"]: testCase["value"]}},
            )

            if "expected_code" in testCase:
                self.assertIn(
                    testCase["expected_code"],
                    str(response.errors[0].message),
                    f"{str(response.errors[0].message)} does not contain code: {testCase['expected_code']} from testCase: {testCase}",
                )
            else:
                self.assertIn(testCase["expected_error"], str(response.errors[0].message))
            self.assertIsNone(response.data["createTask"] if response.data else response.data)

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

        self.assertIsNone(response.errors)

        added_collaboration_tool = response.data["createTask"]
        self.assertIn("id", added_collaboration_tool)
        self.assertEqual(valid_name, added_collaboration_tool["name"])
        self.assertEqual(valid_description, added_collaboration_tool["description"])
        self.assertEqual(valid_visibility, added_collaboration_tool["visibility"])

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

        valid_space_id = str(community.id)
        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"
        valid_location_type = "HYBRID"
        valid_regularity = "REGULARLY"
        valid_contact_email = "email@email.com"
        valid_skills = [str(skill.id)]
        valid_slots_available = 1
        valid_location = "Hamburg, Germany"
        valid_contact_phone = "+49176176176176"

        valid_input = {
            "spaceId": valid_space_id,
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": valid_location_type,
            "regularity": valid_regularity,
            "contactEmail": valid_contact_email,
            "skills": valid_skills,
            "slotsAvailable": valid_slots_available,
            "location": valid_location,
            "contactPhone": valid_contact_phone,
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

        valid_space_id = str(community.id)
        valid_name = "Valid name"
        valid_description = "Valid description"
        valid_visibility = "MEMBERS"
        valid_location_type = "HYBRID"
        valid_regularity = "REGULARLY"
        valid_contact_email = "email@email.com"
        valid_skills = [str(skill.id)]
        valid_slots_available = 1
        valid_location = "Hamburg, Germany"
        valid_contact_phone = "+49176176176176"

        valid_input = {
            "spaceId": valid_space_id,
            "name": valid_name,
            "description": valid_description,
            "visibility": valid_visibility,
            "locationType": valid_location_type,
            "regularity": valid_regularity,
            "contactEmail": valid_contact_email,
            "skills": valid_skills,
            "slotsAvailable": valid_slots_available,
            "location": valid_location,
            "contactPhone": valid_contact_phone,
        }

        response = schema.execute_sync(
            create_task_mutation,
            variable_values={"input": valid_input},
            context_value=BeneDict({"request": {"user": AnonymousUser}}),
        )

        self.assert_is_unauthorized(response)

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

        self.assertIsNone(response.data)
        self.assertIn(
            "Can't delete a task within a community that you do not administrate.", str(response.errors[0].message)
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

        self.assertTrue(response.data["deleteTask"]["success"])
        self.assertIsNone(response.errors)


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
