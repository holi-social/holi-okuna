import json
from typing import List

from benedict import BeneDict
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from graphene.test import Client
from rest_framework import status

from openbook.graphql_schema import (
    schema,
    UpdateConnectionWithUserAction,
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


class ContextWithUser:
    def __init__(self, user):
        self.user = user


class GraphQLTest(TestCase):
    def setUp(self):
        self.graphql = Client(schema)

    fixtures = ["openbook_circles/fixtures/circles.json"]

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
        assert_paged_results_equal(
            results=executed["data"]["userByName"],
            expected_data=[
                {"firstName": u.name, "lastName": u.last_name} for u in expected_users
            ],
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
        self.assertEqual(
            executed["data"]["userByName"]["data"][0]["firstName"], "Peter"
        )
        self.assertEqual(
            executed["data"]["userByName"]["data"][1]["firstName"], "Petra"
        )
        self.assertEqual(
            executed["data"]["userByName"]["data"][2]["firstName"], "Thomas"
        )

    def test_can_update_authenticated_user(self):
        user = make_user(name="Fritz", last_name="Meier")
        pronouns = "She/her"

        assert User.objects.get(username=user.username).profile.pronouns != pronouns

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

        assert graphql_pronouns == persisted_pronouns == pronouns

    def test_can_perform_connection_workflow(self):
        first_user = make_user(name="Fritz", last_name="Meier")
        second_user = make_user(name="Gesine", last_name="Schinder")

        assert not first_user.is_connected_with_user(second_user)

        update_query = """
            mutation test($input: UpdateConnectionWithUserInput) {
                updateConnectionWithUser(input: $input) {
                    id
                }
            }
            """

        connection_request_response = self.graphql.execute(
            update_query,
            context_value=BeneDict({"user": first_user}),
            variable_values={
                "input": {
                    "userId": second_user.username,
                    "action": UpdateConnectionWithUserAction.CONNECT,
                }
            },
        )

        assert (
            connection_request_response["data"]["updateConnectionWithUser"]["id"]
            == second_user.username
        )

        assert second_user.is_pending_confirm_connection_for_user_with_id(first_user.pk)
        assert (
            first_user.get_connection_status_with_user_id(second_user.pk)
            == UserConnectionStatus.REQUESTED
        )

        connection_confirm_response = self.graphql.execute(
            update_query,
            context_value=BeneDict({"user": second_user}),
            variable_values={
                "input": {
                    "userId": first_user.username,
                    "action": UpdateConnectionWithUserAction.CONNECT,
                }
            },
        )

        assert (
            connection_confirm_response["data"]["updateConnectionWithUser"]["id"]
            == first_user.username
        )
        assert first_user.is_fully_connected_with_user_with_id(second_user.pk)
        assert second_user.is_fully_connected_with_user_with_id(first_user.pk)

    def test_can_fetch_post(self):
        posting_user = make_user()
        other_user = make_user(name="Other")

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        post = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        post.comment(text="comment text 1", commenter=other_user)
        post.comment(text="comment text 2", commenter=other_user)

        response = self.graphql.execute(
            f"""
            query {{
                postById(id: "{post.id}") {{
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
            """
        )

        post_data = response["data"]["postById"]
        assert post_data["text"] == post_text
        assert post_data["title"] == post_title
        assert post_data["image"] is None
        assert post_data["creator"]["id"] == str(posting_user.uuid)
        assert post_data["created"] is not None
        assert post_data["numberOfComments"] == 2
        assert post_data["involvedUsers"]["totalResults"] == 2
        assert len(post_data["comments"]) == 2
        assert post_data["comments"][0]["text"] == "comment text 1"
        assert post_data["commenters"]["totalResults"] == 1
        self.assertEqual(
            post_data["commenters"]["data"][0]["firstName"], other_user.name
        )

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

        response = self.graphql.execute(
            f"""
            query {{
                postById(id: "{post.id}") {{
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
                }}
            }}
            """
        )

        post_data = response["data"]["postById"]
        assert post_data["text"] == post_text
        assert post_data["title"] == post_title
        assert image_name in post_data["image"]["url"]
        assert post_data["image"]["width"] == 1
        assert post_data["image"]["height"] == 1
        assert post_data["creator"]["id"] == str(posting_user.uuid)
        assert post_data["created"] is not None

    def test_select_last_insights(self):
        insight_user = make_user()
        posting_user = make_user()
        other_user = make_user()

        post_text = make_fake_post_text()
        post_title = make_fake_post_title()

        now = timezone.now()
        insight1 = Insight.objects.create(
            creator=insight_user,
            title="Insight 1",
            date_published=now - timezone.timedelta(seconds=1),
        )

        post1 = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        post2 = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        post3 = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        insight1.posts.add(post1, post2, post3)

        insight2 = Insight.objects.create(
            creator=posting_user, title="Insight 2", date_published=now
        )
        post4 = posting_user.create_public_post(
            text=post_text,
            title=post_title,
        )
        post4.comment(text=post_text, commenter=other_user)
        insight2.posts.add(post4)

        response = self.graphql.execute(
            f"""
            query {{
                lastInsights {{
                    data {{
                        title
                        numberOfPosts
                        involvedUsers {{
                            totalResults
                            data {{
                              fullName
                            }}
                        }}
                    }}
                }}
            }}
            """
        )

        insights = response["data"]["lastInsights"]["data"]
        assert 2 == len(insights)
        # insight1 = next(i for i in insights if i["title"] == insight1_title)
        # insight2 = next(i for i in insights if i["title"] == insight2_title)
        insight1_result = insights[0]
        assert insight1_result["title"] == insight1.title
        assert insight1_result["numberOfPosts"] == 3
        assert insight1_result["involvedUsers"]["totalResults"] == 2

        insight2_result = insights[1]
        assert insight2_result["title"] == insight2.title
        assert insight2_result["numberOfPosts"] == 1
        assert insight2_result["involvedUsers"]["totalResults"] == 2

    def test_notifications(self):
        followed_user = make_user(name="Peter", last_name="Pep")
        following_user = make_user(name="Other")

        update_query = """
            mutation UpdateConnectionWithUser($input: UpdateConnectionWithUserInput) {
                updateConnectionWithUser(input: $input) {
                    id
                }
            }
            """

        connection_request_response = self.graphql.execute(
            update_query,
            variable_values={
                "input": {
                    "userId": followed_user.username,
                    "action": UpdateConnectionWithUserAction.CONNECT,
                }
            },
            context_value=BeneDict({"user": following_user}),
        )
        self.assertIsNone(connection_request_response.get("errors"))

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
            context_value=BeneDict({"user": followed_user}),
        )
        self.assertIsNone(response.get("errors"))
        self.assertGreaterEqual(response["data"]["notifications"]["totalResults"], 1)
        notifications = response["data"]["notifications"]["data"]
        cr_notification = next(
            n for n in notifications if n["notificationType"] == "CR"
        )
        self.assertEqual(
            cr_notification["owner"]["fullName"], followed_user.profile.full_name()
        )
        self.assertEqual(
            cr_notification["options"]["user"]["fullName"],
            following_user.profile.full_name(),
        )

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
            filter_response = self.graphql.execute(
                filter_query, variable_values=filter_options
            )
            expected_data = list(map(transform_space, expected_spaces))
            assert_paged_results_equal(filter_response["data"]["spaces"], expected_data)

        # Return all spaces for empty filter
        assert_filtered_spaces({}, [space1, space2])

        # Filter by common topic
        assert_filtered_spaces({"topicId": str(topic1.id)}, [space1, space2])

        # Filter by unique topic
        assert_filtered_spaces({"topicId": str(topic2.id)}, [space1])

        # Filter by location
        assert_filtered_spaces({"location": space2.location}, [space2])

        # Filter by topic and location
        assert_filtered_spaces(
            {"topicId": str(topic1.id), "location": space1.location}, [space1]
        )

        # Filter by single skill
        assert_filtered_spaces({"skillIds": [str(skill1.id)]}, [space1])

        # Filter by multiple skills
        assert_filtered_spaces(
            {"skillIds": [str(skill1.id), str(skill3.id)]}, [space1, space2]
        )

        # Filter by skills and location
        assert_filtered_spaces(
            {"skillIds": [str(skill2.id)], "location": space2.location}, [space2]
        )

        # Filter by skills and topics
        assert_filtered_spaces(
            {"skillIds": [str(skill2.id)], "topicId": str(topic2.id)}, [space1]
        )

        # Filter by skills, topics and location
        assert_filtered_spaces(
            {
                "skillIds": [str(skill3.id)],
                "location": space1.location,
                "topicId": str(topic2.id),
            },
            [],
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


def assert_paged_results_equal(results: dict, expected_data: List[dict[str, any]]):
    assert results["totalResults"] == len(expected_data)

    for el in expected_data:
        assert el in results["data"]
