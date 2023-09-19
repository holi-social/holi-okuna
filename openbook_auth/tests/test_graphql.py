import json
import logging
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import call

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from benedict import benedict
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis import geos
from django.core.management import call_command
from django.test import AsyncClient
from django.urls import reverse
from requests.models import Response
from rest_framework import status

from openbook.graphql_schema import schema
from openbook.tests.test_data import geolocation, geolocation_geometry, geolocation_id
from openbook_auth.models import EngagementLevelChoice, User
from openbook_auth.tests.helpers import (
    api_update_authenticated_user_names,
    get_user_connection_status_to_space_data,
    get_user_with_id_raw,
    get_users_by_chat_identities,
)
from openbook_common.tests.helpers import (
    make_authentication_headers_for_user,
    make_community,
    make_fake_post_text,
    make_fake_post_title,
    make_user,
)
from openbook_communities.models import SpaceUserConnectionType
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
class TestUsers:
    @pytest.mark.asyncio
    async def test_get_authenticated_user_returns_self_reference(self, client):
        user = await sync_to_async(make_user)(name="John", last_name="Holi")
        headers = await sync_to_async(make_authentication_headers_for_user)(user)
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
        response = await client.post(
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

    # def test_get_user_by_name_returns_only_matching_users_without_logged_in_user(self):
    #     user = make_user(name="Peter", last_name="Moser")
    #     user2 = make_user(name="Peter", last_name="Muster")
    #     user3 = make_user(name="Peter", last_name="Marker")
    #     expected_users = [user3, user2]
    #     make_user(name="Fritz", last_name="Meier")
    #
    #     executed = async_to_sync(schema.execute)(
    #         """
    #         query {
    #             userByName(substring: "ter M") {
    #                 totalResults
    #                 data {
    #                     firstName
    #                     lastName
    #                 }
    #             }
    #         }
    #         """,
    #         context_value=benedict({"request": {"user": user}}),
    #     )
    #     assert_paged_results_equal(
    #         results=executed.data["userByName"],
    #         expected_data=[{"firstName": u.name, "lastName": u.last_name} for u in expected_users],
    #     )

    # def test_get_user_by_name_first_name_matches_first(self):
    #     make_user(name="Thomas", last_name="Petersen")
    #     make_user(name="Angelika", last_name="Petersen")
    #     make_user(name="Peter", last_name="Muster")
    #     make_user(name="Petra", last_name="Meier")
    #     make_user(name="Fritz", last_name="Meier")
    #
    #     executed = async_to_sync(schema.execute)(
    #         """
    #         query {
    #             userByName(substring: "Pet") {
    #                 totalResults
    #                 data {
    #                     firstName
    #                     lastName
    #                 }
    #             }
    #         }
    #         """,
    #         context_value=benedict({"request": {"user": AnonymousUser}}),
    #     )
    #     assert executed.data["userByName"]["totalResults"] == 4
    #     assert executed.data["userByName"]["data"][0]["firstName"] == "Peter"
    #     assert executed.data["userByName"]["data"][1]["firstName"] == "Petra"
    #     assert executed.data["userByName"]["data"][2]["firstName"] == "Angelika"
    #     assert executed.data["userByName"]["data"][3]["firstName"] == "Thomas"

    def test_get_users_by_chat_identities_success(self):
        user = make_user()
        chat_users = [make_user(identity=f"identity_{i}") for i in range(5)]

        user.block_user_with_id(chat_users[0].id)
        chat_users[1].block_user_with_id(user.id)

        response = get_users_by_chat_identities(user, [chat_user.identity for chat_user in chat_users])

        assert response.errors is None
        assert response.data is not None

        users_by_chat_identities = response.data["usersByChatIdentities"]
        assert users_by_chat_identities["totalResults"] == 3

        response_chat_user_ids = [user["id"] for user in users_by_chat_identities["data"]]
        assert str(chat_users[0].id) not in response_chat_user_ids
        assert str(chat_users[1].id) not in response_chat_user_ids
        assert str(chat_users[2].id) in response_chat_user_ids
        assert str(chat_users[3].id) in response_chat_user_ids
        assert str(chat_users[4].id) in response_chat_user_ids

    def test_get_users_by_chat_identities_error_user_not_logged_in(self):
        chat_users = [make_user(identity=f"identity_{i}") for i in range(5)]

        response = get_users_by_chat_identities(AnonymousUser, [chat_user.identity for chat_user in chat_users])

        print(response.errors)
        assert response.errors is not None
        assert response.data is None

    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("openbook_auth.schema.mutations.publish_user_name_updated_event")
    def test_can_update_authenticated_user(self, mock_publish_user_name_updated_event, mock_patch):
        response = Response()
        response.status_code = 200
        response._content = str.encode(json.dumps({}))
        mock_patch.return_value = response
        user = make_user(name="Fritz", last_name="Meier", identity="fritz")
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

        executed = async_to_sync(schema.execute)(
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
            context_value=benedict({"request": {"user": user}}),
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

    @mock.patch("openbook_auth.tasks.requests.patch")
    def test_can_update_authenticated_user_generates_an_identity(self, ory_patch_mock):
        ory_patch_mock_response = Response()
        ory_patch_mock_response.status_code = 200
        ory_patch_mock_response._content = str.encode(json.dumps({}))
        ory_patch_mock.return_value = ory_patch_mock_response
        user = make_user()
        user.identity = None

        result = api_update_authenticated_user_names(user, "Fritz", "Meier")

        assert result.errors is None

        expected_ory_call_body = [
            {"op": "add", "path": "/traits/identity", "value": "fritz"},
        ]

        ory_patch_mock.assert_called_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=expected_ory_call_body,
        )

        result = result.data["updateAuthenticatedUser"]
        persisted_user = User.objects.get(username=user.username)

        assert "fritz" == persisted_user.identity
        assert "fritz" == result["identity"]

        # test it only registers identity once
        result = api_update_authenticated_user_names(user, "Hans", "Meier")

        assert result.errors is None

        result = result.data["updateAuthenticatedUser"]
        persisted_user = User.objects.get(username=user.username)
        assert "fritz" == persisted_user.identity
        assert "fritz" == result["identity"]

    @mock.patch("openbook_auth.tasks.requests.patch")
    def test_api_registers_new_user_with_already_taken_identity_for_a_user(self, ory_patch_mock):
        ory_update_response_stub = Response()
        ory_update_response_stub.status_code = 200
        ory_update_response_stub._content = str.encode(json.dumps({}))
        ory_patch_mock.return_value = ory_update_response_stub

        make_user(name="Fritz", last_name="Meier", identity="fritz")
        new_fritz = make_user(name="Fritz", last_name="Hansen")
        new_fritz.identity = None

        result = api_update_authenticated_user_names(new_fritz, "Fritz", "Hansen")

        assert result.errors is None
        assert result.data["updateAuthenticatedUser"]["identity"] == "fritzhansen"

        expected_json_body = [{"op": "add", "path": "/traits/identity", "value": "fritzhansen"}]

        ory_patch_mock.assert_called_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{new_fritz.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=expected_json_body,
        )

    @mock.patch("openbook_auth.tasks.requests.patch")
    def test_api_registers_new_user_with_ory_identity_collision(self, ory_patch_mock):
        ory_update_user_name_success = Response()
        ory_update_user_name_success.status_code = 200
        ory_update_user_name_success._content = str.encode(json.dumps({}))

        ory_update_identity_conflict = Response()
        ory_update_identity_conflict.status_code = 409
        ory_update_identity_conflict._content = str.encode(json.dumps({"error": {"message": "Error Message"}}))

        ory_update_identity_success = Response()
        ory_update_identity_success.status_code = 200
        ory_update_identity_success._content = str.encode(json.dumps({}))

        ory_patch_mock.side_effect = [
            ory_update_user_name_success,
            ory_update_identity_conflict,
            ory_update_identity_success,
        ]

        new_user = make_user()
        new_user.identity = None

        result = api_update_authenticated_user_names(new_user, "Fritz", "Hansen")

        assert result.errors is None
        assert result.data["updateAuthenticatedUser"]["identity"] == "fritzhansen"

        ory_patch_mock.assert_has_calls(
            [
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/traits/identity", "value": "fritz"},
                    ],
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/traits/identity", "value": "fritzhansen"},
                    ],
                ),
            ]
        )

    @mock.patch("openbook_auth.tasks.requests.patch")
    def test_api_registers_new_user_with_ory_identity_collision_only_first_name(self, ory_patch_mock):
        ory_update_user_name_success = Response()
        ory_update_user_name_success.status_code = 200
        ory_update_user_name_success._content = str.encode(json.dumps({}))

        ory_update_identity_conflict = Response()
        ory_update_identity_conflict.status_code = 409
        ory_update_identity_conflict._content = str.encode(json.dumps({"error": {"message": "Error Message"}}))

        ory_update_identity_success = Response()
        ory_update_identity_success.status_code = 200
        ory_update_identity_success._content = str.encode(json.dumps({}))

        ory_patch_mock.side_effect = [
            ory_update_user_name_success,
            ory_update_identity_conflict,
            ory_update_identity_success,
        ]

        new_user = make_user()
        new_user.identity = None

        result = api_update_authenticated_user_names(new_user, "Fritz", "")

        assert result.errors is None
        assert result.data["updateAuthenticatedUser"]["identity"] == "fritz1"

        ory_patch_mock.assert_has_calls(
            [
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/traits/identity", "value": "fritz"},
                    ],
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/traits/identity", "value": "fritz1"},
                    ],
                ),
            ]
        )

    @mock.patch("openbook_auth.tasks.requests.patch")
    def test_api_registers_new_user_with_ory_identity_multiple_collision(self, ory_patch_mock):
        ory_update_user_name_success = Response()
        ory_update_user_name_success.status_code = 200
        ory_update_user_name_success._content = str.encode(json.dumps({}))

        ory_update_identity_conflict = Response()
        ory_update_identity_conflict.status_code = 409
        ory_update_identity_conflict._content = str.encode(json.dumps({"error": {"message": "Error Message"}}))

        ory_update_identity_success = Response()
        ory_update_identity_success.status_code = 200
        ory_update_identity_success._content = str.encode(json.dumps({}))

        ory_patch_mock.side_effect = [
            ory_update_user_name_success,
            ory_update_identity_conflict,
            ory_update_identity_conflict,
            ory_update_identity_conflict,
            ory_update_identity_success,
        ]

        new_user = make_user()
        new_user.identity = None

        result = api_update_authenticated_user_names(new_user, "Fritz", "Hansen")

        assert result.errors is None
        assert result.data["updateAuthenticatedUser"]["identity"] == "fritzhansen2"

        ory_patch_mock.assert_has_calls(
            [
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/traits/identity", "value": "fritz"},
                    ],
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/traits/identity", "value": "fritzhansen"},
                    ],
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/traits/identity", "value": "fritzhansen1"},
                    ],
                ),
            ]
        )

    @mock.patch("openbook_auth.tasks.requests.delete")
    @mock.patch("openbook_auth.schema.mutations.publish_user_deleted_event")
    @mock.patch("openbook_auth.schema.mutations.publish_space_deleted_event")
    def test_can_delete_authenticated_user(
        self, mock_publish_space_deleted_event, mock_publish_user_deleted_event, mock_delete
    ):
        response = Response()
        response.status_code = 204
        response._content = str.encode(json.dumps({}))
        mock_delete.return_value = response

        user = make_user(name="Fritz", last_name="Meier")
        space = make_community(creator=user)

        mutation_response = async_to_sync(schema.execute)(
            """
            mutation test {
                deleteAuthenticatedUser {
                    success
                }
            }
            """,
            context_value=benedict({"request": {"user": user}}),
        )
        mock_delete.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
        )

        assert mutation_response.data["deleteAuthenticatedUser"]["success"] is True

        mock_publish_user_deleted_event.assert_called_once_with(user=user)
        mock_publish_space_deleted_event.assert_called_once_with(space)

    def test_block_user(self):
        blocking_user = make_user(name="BlockingUser")
        two_hours_ago = datetime.now() - timedelta(hours=2)
        blocked_user = make_user(name="BlockedUser", date_joined=two_hours_ago)
        other_user = make_user(name="OtherUser", date_joined=two_hours_ago)
        other_user.save()

        other_post = other_user.create_post(
            text=(make_fake_post_text()), title=(make_fake_post_title()), is_public=True
        )
        other_post.comment(text=f"comment text 1", commenter=blocked_user)

        blocked_post = blocked_user.create_post(
            text=(make_fake_post_text()), title=(make_fake_post_title()), is_public=True
        )
        blocked_post.comment(text=f"comment text 1", commenter=other_user)

        response = async_to_sync(schema.execute)(
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
            context_value=benedict({"request": {"user": blocking_user}}),
        )
        assert response.data["userSuggestions"]["totalResults"] == 2

        response = async_to_sync(schema.execute)(
            """
            mutation ($userId: UUID!) {
                blockUser(userId: $userId) {
                    success
                }
            }
            """,
            context_value=benedict({"request": {"user": blocking_user}}),
            variable_values=benedict(
                {
                    "userId": blocked_user.username,
                }
            ),
        )

        blocked_post_raw = get_post_with_id_raw(blocked_post, blocking_user)
        assert blocked_post_raw.data["postById"] is None
        other_post_data = get_post_with_id_data(other_post, blocking_user)
        assert other_post_data["involvedUsers"]["totalResults"] == 1
        assert other_post_data["numberOfComments"] == 0
        assert other_post_data["commenters"]["totalResults"] == 0

        assert response.errors is None
        assert response.data["blockUser"]["success"] is True

        response_after_blocking = get_user_with_id_raw(blocked_user, blocking_user)
        assert response_after_blocking.data["userById"] is None

        response_after_blocking = get_user_with_id_raw(blocking_user, blocked_user)
        assert response_after_blocking.data["userById"] is None

        response = async_to_sync(schema.execute)(
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
            context_value=benedict({"request": {"user": blocking_user}}),
        )
        assert response.data["userSuggestions"]["totalResults"] == 1
        assert response.data["userSuggestions"]["data"][0]["fullName"] == "OtherUser"

    def test_user_connection_status_to_space(self):
        user = make_user()
        creator = make_user()
        member = make_user()
        invitee = make_user()
        follower = make_user()
        membership_requestor = make_user()
        space = make_community(creator=creator)
        space.add_member(member)
        space.create_invite(creator, invitee)
        space.add_membership_request(membership_requestor)
        follower.enable_new_post_notifications_for_community_with_name(space.name)

        assert get_user_connection_status_to_space_data(user, space) == []
        assert get_user_connection_status_to_space_data(creator, space) == [
            SpaceUserConnectionType.CREATOR.value,
            SpaceUserConnectionType.MEMBER.value,
            SpaceUserConnectionType.ADMINISTRATOR.value,
        ]
        assert get_user_connection_status_to_space_data(member, space) == [SpaceUserConnectionType.MEMBER.value]
        assert get_user_connection_status_to_space_data(invitee, space) == [
            SpaceUserConnectionType.MEMBERSHIP_INVITEE.value
        ]
        assert get_user_connection_status_to_space_data(follower, space) == [SpaceUserConnectionType.FOLLOWER.value]
        assert get_user_connection_status_to_space_data(membership_requestor, space) == [
            SpaceUserConnectionType.MEMBERSHIP_REQUESTOR.value
        ]
