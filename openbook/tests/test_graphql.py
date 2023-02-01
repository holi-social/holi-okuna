import json
import logging
import unittest
from typing import List, Optional
from uuid import UUID, uuid4

from benedict import BeneDict
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from graphene.test import Client
from rest_framework import status

from openbook.graphql_schema import (
    schema,
    UpdateConnectionAction,
    SpaceUserConnectionType,
    ContentType,
)
from openbook_auth.models import User, UserConnectionStatus
from openbook_communities.models import Community
from openbook_common.tests.helpers import (
    make_user,
    make_authentication_headers_for_user,
    make_fake_post_text,
    make_fake_post_title,
    make_community,
    make_community_task,
    make_topic,
    make_skill,
    simple_jpeg_bytes,
)
from openbook_insights.models import Insight
from openbook_moderation.models import ModeratedObject

logger = logging.getLogger(__name__)


class ContextWithUser:
    def __init__(self, user):
        self.user = user


class GraphQLTest(TestCase):
    def setUp(self):
        self.graphql = Client(schema)

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

        executed = self.graphql.execute(
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
            context_value=BeneDict({"user": user}),
        )
        self.assert_paged_results_equal(
            results=executed["data"]["userByName"],
            expected_data=[{"firstName": u.name, "lastName": u.last_name} for u in expected_users],
        )

    def test_get_user_by_name_first_name_matches_first(self):
        make_user(name="Thomas", last_name="Petersen"),
        make_user(name="Peter", last_name="Muster"),
        make_user(name="Petra", last_name="Meier"),
        make_user(name="Fritz", last_name="Meier")

        executed = self.graphql.execute(
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
            """
        )
        self.assertEqual(executed["data"]["userByName"]["totalResults"], 3)
        self.assertEqual(executed["data"]["userByName"]["data"][0]["firstName"], "Peter")
        self.assertEqual(executed["data"]["userByName"]["data"][1]["firstName"], "Petra")
        self.assertEqual(executed["data"]["userByName"]["data"][2]["firstName"], "Thomas")

    def test_can_update_authenticated_user(self):
        user = make_user(name="Fritz", last_name="Meier")
        pronouns = "She/her"

        self.assertNotEqual(User.objects.get(username=user.username).profile.pronouns, pronouns)

        executed = self.graphql.execute(
            """
            mutation test($input: UpdateAuthenticatedUserInput) {
                updateAuthenticatedUser(input: $input) {
                    id
                    pronouns
                }
            }
            """,
            context_value=BeneDict({"user": user}),
            variable_values={"input": {"pronouns": pronouns}},
        )
        graphql_pronouns = executed["data"]["updateAuthenticatedUser"]["pronouns"]
        persisted_pronouns = User.objects.get(username=user.username).profile.pronouns

        self.assertEqual(graphql_pronouns, persisted_pronouns)
        self.assertEqual(graphql_pronouns, pronouns)

    def test_can_perform_connection_workflow(self):
        first_user = make_user(name="Fritz", last_name="Meier")
        second_user = make_user(name="Gesine", last_name="Schinder")

        self.assertFalse(first_user.is_connected_with_user(second_user))

        connection_request_response = self.connect_to_user(first_user, second_user)

        self.assertEqual(
            connection_request_response["data"]["updateConnectionWithUser"]["id"],
            second_user.username,
        )

        self.assertTrue(second_user.is_pending_confirm_connection_for_user_with_id(first_user.pk))
        self.assertEqual(
            first_user.get_connection_status_with_user_id(second_user.pk),
            UserConnectionStatus.REQUESTED,
        )

        connection_confirm_response = self.connect_to_user(second_user, first_user)

        self.assertEqual(
            connection_confirm_response["data"]["updateConnectionWithUser"]["id"],
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

        post_data = response["data"]["postById"]
        self.assertEqual(post_data, None)
        self.assertEqual(response["errors"][0]["message"], "Post not found")

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
            date_published=now - timezone.timedelta(seconds=1),
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

        insight2 = Insight.objects.create(creator=posting_user, title="Insight 2", date_published=now)
        post4 = posting_user.create_public_post(
            text=post_text_public,
            title=post_title_public,
        )
        post4.comment(text=post_text_public, commenter=other_user)
        insight2.posts.add(post4)

        response = self.graphql.execute(
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
            context_value=BeneDict({"user": AnonymousUser}),
        )

        insights = response["data"]["lastInsights"]["data"]
        self.assertEqual(2, len(insights))
        # insight1 = next(i for i in insights if i["title"] == insight1_title)
        # insight2 = next(i for i in insights if i["title"] == insight2_title)
        insight1_result = insights[0]
        self.assertEqual(insight1_result["title"], insight1.title)
        self.assertEqual(insight1_result["numberOfPosts"], 2)
        self.assertEqual(insight1_result["posts"][0]["title"], post_title_public)
        self.assertEqual(insight1_result["posts"][1]["title"], post_title_public)
        self.assertEqual(insight1_result["involvedUsers"]["totalResults"], 2)

        insight2_result = insights[1]
        self.assertEqual(insight2_result["title"], insight2.title)
        self.assertEqual(insight2_result["numberOfPosts"], 1)
        self.assertEqual(insight2_result["involvedUsers"]["totalResults"], 2)

    def test_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")

        self.connect_to_user(following_user, followed_user)

        response = self.get_notifications(followed_user)
        self.assertGreaterEqual(response["data"]["notifications"]["totalResults"], 1)
        notifications = response["data"]["notifications"]["data"]
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

        notifications = self.get_notifications(followed_user)["data"]["notifications"]["data"]
        connection_accepted_notification = next(n for n in notifications if n["notificationType"] == "CA")
        self.assertEqual(
            connection_accepted_notification["options"]["user"]["fullName"],
            following_user.profile.full_name(),
        )

        notifications = self.get_notifications(following_user)["data"]["notifications"]["data"]
        connection_confirmed_notification = next(n for n in notifications if n["notificationType"] == "CC")
        self.assertEqual(
            connection_confirmed_notification["options"]["user"]["fullName"],
            followed_user.profile.full_name(),
        )

    def connect_to_user(self, following_user, followed_user):
        connection_request_response = self.graphql.execute(
            """
            mutation UpdateConnectionWithUser($input: UpdateConnectionWithUserInput) {
                updateConnectionWithUser(input: $input) {
                    id
                }
            }
            """,
            variable_values={
                "input": {
                    "userId": followed_user.username,
                    "action": UpdateConnectionAction.CONNECT._value_,
                }
            },
            context_value=BeneDict({"user": following_user}),
        )
        self.assertIsNone(connection_request_response.get("errors"))
        return connection_request_response

    def test_filters_for_spaces(self):
        topic1 = make_topic()
        topic2 = make_topic()
        space1 = make_community(topics=[topic1, topic2], location="Location1")
        space2 = make_community(topics=[topic1], location="Location2")
        skill1 = make_skill()
        skill2 = make_skill()
        skill3 = make_skill()
        make_community_task(space1, skills=[skill1, skill2])
        make_community_task(space2, skills=[skill2, skill3])

        filter_query = """
            query($topicId: UUID, $location: String, $skillIds: [UUID]) {
                spaces(topicId: $topicId, location: $location, skillIds: $skillIds) {
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
            filter_response = self.graphql.execute(filter_query, variable_values=filter_options)
            expected_data = list(map(transform_space, expected_spaces))
            self.assert_paged_results_equal(filter_response["data"]["spaces"], expected_data)

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
            filter_response = self.graphql.execute(filter_query, variable_values=filter_options)
            expected_data = list(map(transform_space, expected_spaces))
            self.assert_paged_results_equal(
                filter_response["data"]["discoverSpaces"][0]["spaces"],
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

        filter_response = self.graphql.execute(
            filter_query, variable_values={"topicIds": [str(topic1.id), str(topic2.id)]}
        )
        self.assertEqual(len(filter_response["data"]["discoverSpaces"]), 2)
        self.assert_paged_results_equal(
            filter_response["data"]["discoverSpaces"][0]["spaces"],
            list(map(transform_space, [space1, space2])),
        )
        self.assert_paged_results_equal(
            filter_response["data"]["discoverSpaces"][1]["spaces"],
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
        response = self.graphql.execute(filter_query)["data"]["spaces"]["data"]
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

        response = self.graphql.execute(
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
            context_value=BeneDict({"user": creator1}),
        )["data"]["mySpaces"]

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

    def test_space_membership_request(self):
        membership_requester = make_user()
        space_creator = make_user()
        space = make_community(creator=space_creator)

        def member_result(user):
            return {
                "user": {"id": user.username},
                "isAdministrator": True,
                "isModerator": False,
            }

        # Preconditions
        pre_join_space = self.get_space_for_user(membership_requester, space)
        self.assertEqual(pre_join_space["connectionStatusToMyself"], [])
        self.assert_paged_results_equal(pre_join_space["members"], [member_result(space_creator)])

        # Send Join Request
        after_request_space = self.mutate_update_space_user_connection(
            auth_user=membership_requester,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )

        self.assertCountEqual(
            after_request_space["connectionStatusToMyself"],
            [SpaceUserConnectionType.MEMBER.value, SpaceUserConnectionType.FOLLOWER.value],
        )

        # TODO Un-Comment this after Auto-Join of Spaces is removed again
        #
        # self.assertCountEqual(
        #     after_request_space["connectionStatusToMyself"],
        #     [SpaceUserConnectionType.FOLLOWER.value, SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value],
        # )
        #
        # # Notification received
        # request_notification = space_creator.get_notifications(
        #     types=[Notification.COMMUNITY_MEMBERSHIP_REQUEST]
        # ).first()
        # self.assertEqual(request_notification.get_options()["space"], space)
        # self.assertEqual(request_notification.get_options()["user"], membership_requester)
        #
        # # Revoke from User
        # after_revocation_space = self.mutate_update_space_user_connection(
        #     auth_user=membership_requester,
        #     space_id=space.id,
        #     connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
        #     connect_action=UpdateConnectionAction.DISCONNECT,
        # )
        #
        # self.assertEqual(after_revocation_space["connectionStatusToMyself"], [])
        #
        # # Notification cleared
        # self.assertFalse(space_creator.get_notifications(types=[Notification.COMMUNITY_MEMBERSHIP_REQUEST]).exists())

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

        response = self.graphql.execute(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"user": reporting_user}),
            variable_values=BeneDict(
                {
                    "objectId": str(post.id),
                    "contentType": ContentType.POST.value,
                    "description": "report",
                }
            ),
        )

        self.assertIsNone(response.get("errors"))
        self.assertEqual(response["data"]["reportContent"]["success"], True)

        self.assertEqual(reporting_user.can_see_post(post), False)
        self.assertEqual(other_user.can_see_post(post), True)

        response = self.get_post_with_id_raw(post, reporting_user)
        self.assertIsNone(response["data"]["postById"])
        self.assertFalse(reporting_user.can_see_post(post))
        self.assertTrue(other_user.can_see_post(post))

        post_data = self.get_post_with_id_data(post, other_user)
        self.assertEqual(post_data["id"], str(post.id))

        approve_verify_moderated_object(post.id, posting_user)

        response = self.get_post_with_id_raw(post, other_user)
        self.assertFalse(other_user.can_see_post(post))
        self.assertIsNone(response["data"]["postById"])

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

        response = self.graphql.execute(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"user": reporting_user}),
            variable_values=BeneDict(
                {
                    "objectId": str(comment.id),
                    "contentType": ContentType.POST_COMMENT.value,
                    "description": "report",
                }
            ),
        )

        self.assertIsNone(response.get("errors"))
        self.assertEqual(response["data"]["reportContent"]["success"], True)

        post_data = self.get_post_with_id_data(post, reporting_user)
        self.assertEqual(len(post_data["comments"]), 0)

        post_data = self.get_post_with_id_data(post, other_user)
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

        response = self.graphql.execute(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"user": reporting_user}),
            variable_values=BeneDict(
                {
                    "objectId": str(user.username),
                    "contentType": ContentType.USER.value,
                    "description": "report",
                }
            ),
        )

        self.assertIsNone(response.get("errors"))
        self.assertEqual(response["data"]["reportContent"]["success"], True)

        response = self.get_user_with_id_raw(user, reporting_user)
        self.assertIsNone(response["data"]["userById"])

        user_before_approve = self.get_user_with_id_data(user, other_user)
        self.assertEqual(user_before_approve["id"], user.username)
        user_before_approve = self.get_user_with_id_data(user)
        self.assertEqual(user_before_approve["id"], user.username)

        approve_verify_moderated_object(user.id, user)

        response_after_approve = self.get_user_with_id_raw(user, other_user)
        self.assertIsNone(response_after_approve["data"]["userById"])
        response_after_approve = self.get_user_with_id_raw(user)
        self.assertIsNone(response_after_approve["data"]["userById"])

    def test_report_space(self):
        space_user = make_user()
        space_user.is_moderator = True
        reporting_user = make_user(name="ReportingUser")
        other_user = make_user(name="OtherUser")

        space = make_community(creator=space_user)

        response = self.graphql.execute(
            """
            mutation ($objectId: UUID!, $contentType: ContentType!, $description: String) {
                reportContent(objectId: $objectId, contentType: $contentType, description: $description) {
                    success
                }
            }
            """,
            context_value=BeneDict({"user": reporting_user}),
            variable_values=BeneDict(
                {
                    "objectId": str(space.id),
                    "contentType": ContentType.SPACE.value,
                    "description": "report",
                }
            ),
        )

        self.assertIsNone(response.get("errors"))
        self.assertEqual(response["data"]["reportContent"]["success"], True)

        response = self.graphql.execute(
            f"""
            query {{
                spaceById(id: "{space.id}") {{
                    id
                }}
            }}
            """,
            context_value=BeneDict({"user": reporting_user}),
        )
        self.assertIsNone(response["data"]["spaceById"])

        response = self.graphql.execute(
            f"""
            query {{
                spaceById(id: "{space.id}") {{
                    id
                }}
            }}
            """,
            context_value=BeneDict({"user": other_user}),
        )
        self.assertIsNone(response.get("errors"))
        self.assertEqual(len(response["data"]["spaceById"]), 1)
        self.assertEqual(response["data"]["spaceById"]["id"], str(space.id))

        approve_verify_moderated_object(space.id, space_user)

        response = self.graphql.execute(
            f"""
            query {{
                spaceById(id: "{space.id}") {{
                    id
                }}
            }}
            """,
            context_value=BeneDict({"user": other_user}),
        )
        self.assertIsNone(response["data"]["spaceById"])

    def test_block_user(self):
        blocking_user = make_user(name="BlockingUser")
        blocked_user = make_user(name="OtherUser")

        response = self.graphql.execute(
            """
            mutation ($userId: UUID!) {
                blockUser(userId: $userId) {
                    success
                }
            }
            """,
            context_value=BeneDict({"user": blocking_user}),
            variable_values=BeneDict(
                {
                    "userId": blocked_user.username,
                }
            ),
        )

        self.assertIsNone(response.get("errors"))
        self.assertEqual(response["data"]["blockUser"]["success"], True)

        response_after_blocking = self.get_user_with_id_raw(blocked_user, blocking_user)
        self.assertIsNone(response_after_blocking["data"]["userById"])

        response_after_blocking = self.get_user_with_id_raw(blocking_user, blocked_user)
        self.assertIsNone(response_after_blocking["data"]["userById"])

    # Utility methods

    def get_user_with_id_data(self, user_to_get, calling_user=None):
        response = self.get_user_with_id_raw(user_to_get, calling_user)
        self.assertIsNone(response.get("errors"))
        return response["data"]["userById"]

    def get_user_with_id_raw(self, user_to_get, calling_user=None):
        return self.graphql.execute(
            f"""
            query {{
                userById(id: "{user_to_get.username}") {{
                    id
                }}
            }}
            """,
            context_value=BeneDict({"user": calling_user or AnonymousUser}),
        )

    def get_post_with_id_data(self, post, user=None):
        response = self.get_post_with_id_raw(post, user)
        self.assertIsNone(response.get("errors"))
        return response["data"]["postById"]

    def get_post_with_id_raw(self, post, user=None):
        return self.graphql.execute(
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
                }}
            }}
            """,
            context_value=BeneDict({"user": user or AnonymousUser}),
        )

    def mutate_update_space_user_connection(
        self,
        auth_user: User,
        space_id: UUID,
        connection_type: SpaceUserConnectionType,
        connect_action: UpdateConnectionAction,
        user_id: Optional[UUID] = None,
    ):
        response = self.graphql.execute(
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
                            isModerator
                        }
                    }
                    connectionStatusToMyself
                }
            }
            """,
            context_value=BeneDict({"user": auth_user}),
            variable_values=BeneDict(
                {
                    "spaceId": str(space_id),
                    "userId": str(user_id) if user_id else None,
                    "type": connection_type.value,
                    "action": connect_action.value,
                }
            ),
        )

        self.assertIsNone(response.get("errors"))
        return response["data"]["updateSpaceUserConnection"]

    def get_space_for_user(self, user: User, space: Community):
        response = self.graphql.execute(
            """
            query($id:UUID) {
                spaceById(id:$id) {
                    id
                    name
                    members {
                        totalResults
                        data {
                            user {
                                id
                            }
                            isAdministrator
                            isModerator
                        }
                    }
                    connectionStatusToMyself
                }
            }
            """,
            variables={"id": str(space.id)},
            context=BeneDict({"user": user}),
        )

        self.assertIsNone(response.get("errors"))
        return response["data"]["spaceById"]

    def get_notifications(self, user):
        response = self.graphql.execute(
            """
            query {
                notifications {
                    totalResults
                    data {
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
                        }
                    }
                }
            }
            """,
            context_value=BeneDict({"user": user}),
        )
        self.assertIsNone(response.get("errors"))
        return response

    def assert_paged_results_equal(self, results: dict, expected_data: List[dict[str, any]]):
        self.assertEqual(results["totalResults"], len(expected_data))

        for el in expected_data:
            self.assertIn(el, results["data"])

    def test_validate_space(self):
        community = make_community(name="existing_space")
        topic_ids = [str(make_topic().id) for x in range(7)]
        validate_space_mutation = """
            mutation test($input: ValidateSpaceInput) {
                validateSpace(input: $input) {
                    success
                }
            }
            """
        valid_input = {"title": "valid", "description": "valid"}
        full_valid_input = valid_input | {"topics": topic_ids[:2]}
        invalid_uuid = str(uuid4())

        expectedErrors = [
            {"full_input": {"description": "valid"}, "expected_code": "required"},
            {"full_input": {"title": "valid"}, "expected_code": "required"},
            {"input": {"title": None}, "expected_code": "null"},
            {"input": {"description": None}, "expected_code": "null"},
            {"input": {"title": ""}, "expected_code": "blank"},
            {"input": {"description": ""}, "expected_code": "blank"},
            {"input": {"title": "f"}, "expected_code": "min_length"},
            {"input": {"title": "f" * 61}, "expected_code": "max_length"},
            {"input": {"description": "f" * 601}, "expected_code": "max_length"},
            {"input": {"title": '%&$"#'}, "expected_error": "Can not create valid community name from title."},
            {"input": {"title": community.name}, "expected_error": "Community name already taken."},
            {"input": {"topics": None}, "expected_code": "null"},
            {"input": {"topics": []}, "expected_code": "min_length"},
            {"input": {"topics": topic_ids}, "expected_code": "max_length"},
            {"input": {"topics": [invalid_uuid]}, "expected_error": f"No topic with the id '{invalid_uuid}' found."},
        ]

        for testCase in expectedErrors:
            response = self.graphql.execute(
                validate_space_mutation,
                variable_values={
                    "input": testCase["full_input"] if "full_input" in testCase else valid_input | testCase["input"],
                },
            )

            expected_error = (
                testCase["expected_error"] if "expected_error" in testCase else f'code=\'{testCase["expected_code"]}\''
            )
            self.assertIn(expected_error, str(response["errors"][0]["message"]))
            self.assertIsNone(response["data"]["validateSpace"])

        response = self.graphql.execute(
            validate_space_mutation,
            variable_values={"input": full_valid_input},
        )

        self.assertTrue(response["data"]["validateSpace"]["success"])
        self.assertNotIn("errors", response)


def approve_verify_moderated_object(object_id, user):
    moderated_object = ModeratedObject.objects.filter(object_id=object_id).first()
    user.approve_moderated_object(moderated_object)
    user.verify_moderated_object(moderated_object)
