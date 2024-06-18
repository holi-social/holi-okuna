# ruff: noqa

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
from django.http import HttpRequest
from django.test import AsyncClient
from django.urls import reverse
from requests.models import Response
from rest_framework import status
from structlog.testing import capture_logs

from openbook.graphql_schema import schema
from openbook.tests.test_data import geolocation, geolocation_geometry, geolocation_id
from openbook_auth.models import EngagementLevelChoice, User
from openbook_auth.tests.helpers import (
    api_update_authenticated_user_names_data,
    get_user_connection_status_to_space_data,
    get_user_with_id_raw,
    get_users_by_chat_identities,
    get_connected_users,
    get_connected_users_raw,
)
from openbook_common.enums import FeatureToggleName, FeatureToggleType
from openbook_common.models import FeatureToggle
from openbook_common.tests.helpers import (
    assert_is_unauthorized,
    make_authentication_headers_for_user,
    make_community,
    make_fake_post_text,
    make_fake_post_title,
    make_user,
    assert_paged_results_equal,
    assert_is_forbidden,
)
from openbook_communities.enums import UpdateConnectionAction
from openbook_communities.models import SpaceUserConnectionType
from openbook_communities.tests.helpers import (
    mutate_update_space_user_connection_data,
)
from openbook_connections.tests.helpers import connect_to_user
from openbook_notifications.enums import NotificationProvider
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
    @pytest.fixture(autouse=True)
    def setup(self):
        notifications_toggle = FeatureToggle.objects.create(
            name=FeatureToggleName.NOTIFICATIONS.value, status=FeatureToggleType.PRODUCTION
        )
        yield
        notifications_toggle.delete()

    # TODO HOLI-8088 remove test once get_authenticated_user is removed
    @pytest.mark.asyncio
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    async def test_get_authenticated_user_returns_self_reference(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, client
    ):
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

        mock_create_or_update_subscriber.assert_called_once_with(
            user=user, locale=mock_get_language_from_request.return_value
        )

    @pytest.mark.asyncio
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    async def test_get_authenticated_user_v2_returns_self_reference(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, client
    ):
        user = await sync_to_async(make_user)(name="John", last_name="Holi New")
        headers = await sync_to_async(make_authentication_headers_for_user)(user)
        endpoint = reverse("graphql-endpoint")
        graphql_query = """
            query {
                authenticatedUserV2 {
                    id
                    fullName
                    engagementLevel
                    trackingConsentAnalytics
                    trackingConsentPersonalization
                    isStaff
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

        authenticated_user = json.loads(response.content)["data"]["authenticatedUserV2"]
        assert authenticated_user["id"] == str(user.uuid)
        assert authenticated_user["fullName"] == user.profile.full_name()
        assert authenticated_user["engagementLevel"] == user.profile.engagement_level
        assert authenticated_user["trackingConsentAnalytics"] == user.tracking_consent_analytics
        assert authenticated_user["trackingConsentPersonalization"] == user.tracking_consent_personalization
        assert authenticated_user["isEmployee"] == user.is_employee

        mock_create_or_update_subscriber.assert_called_once_with(
            user=user, locale=mock_get_language_from_request.return_value
        )

    def test_get_user_by_name_returns_only_matching_users_without_logged_in_user(self):
        user = make_user(name="Peter", last_name="Moser")
        user2 = make_user(name="Peter", last_name="Muster")
        user3 = make_user(name="Peter", last_name="Marker")
        expected_users = [user3, user2]
        make_user(name="Fritz", last_name="Meier")

        executed = async_to_sync(schema.execute)(
            """
            query {
                userByName(substring: "ter M") {
                    totalResults
                    data {
                        firstName
                        lastName
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": user}}),
        )
        assert_paged_results_equal(
            results=executed.data["userByName"],
            expected_data=[{"firstName": u.name, "lastName": u.last_name} for u in expected_users],
        )

    def test_get_user_by_id_returns_no_private_fields(self):
        user = make_user(name="Peter", last_name="Moser")
        user.update(tracking_consent_analytics=True, save=True)
        user.update(tracking_consent_personalization=False, save=True)
        executed = async_to_sync(schema.execute)(
            """
            query UserById($userId: UUID!) {
                userById(id: $userId) {
                    firstName
                    lastName
                    trackingConsentAnalytics
                }
            }
            """,
            context_value=benedict({"request": {"user": AnonymousUser}}),
            variable_values={"userId": str(user.id)},
        )
        assert "Cannot query field 'trackingConsentAnalytics' on type 'User'" in str(executed.errors)

    def test_get_user_by_name_first_name_matches_first(self):
        make_user(name="Thomas", last_name="Petersen")
        make_user(name="Angelika", last_name="Petersen")
        make_user(name="Peter", last_name="Muster")
        make_user(name="Petra", last_name="Meier")
        make_user(name="Fritz", last_name="Meier")

        executed = async_to_sync(schema.execute)(
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
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert executed.data["userByName"]["totalResults"] == 4
        assert executed.data["userByName"]["data"][0]["firstName"] == "Peter"
        assert executed.data["userByName"]["data"][1]["firstName"] == "Petra"
        assert executed.data["userByName"]["data"][2]["firstName"] == "Angelika"
        assert executed.data["userByName"]["data"][3]["firstName"] == "Thomas"

    def test_get_users_by_chat_identities_success(self):
        user = make_user(identity="user_identity")
        chat_users = [make_user(identity=f"identity_{i}") for i in range(5)]

        user.block_user_with_id(chat_users[0].id)
        chat_users[1].block_user_with_id(user.id)

        response = get_users_by_chat_identities(
            user, [chat_user.identity for chat_user in chat_users] + [user.identity]
        )

        assert response.errors is None
        assert response.data is not None

        users_by_chat_identities = response.data["usersByChatIdentities"]
        assert users_by_chat_identities["totalResults"] == 6  # total count includes blocked ones

        response_chat_user_ids = [user["id"] for user in users_by_chat_identities["data"]]
        assert str(chat_users[0].id) not in response_chat_user_ids
        assert str(chat_users[1].id) not in response_chat_user_ids
        assert str(chat_users[2].id) in response_chat_user_ids
        assert str(chat_users[3].id) in response_chat_user_ids
        assert str(chat_users[4].id) in response_chat_user_ids
        assert str(user.id) in response_chat_user_ids
        assert len(response_chat_user_ids) == 4

    def test_get_users_by_chat_identities_error_user_not_logged_in(self):
        chat_users = [make_user(identity=f"identity_{i}") for i in range(5)]

        response = get_users_by_chat_identities(AnonymousUser, [chat_user.identity for chat_user in chat_users])

        print(response.errors)
        assert response.errors is not None
        assert response.data is None

    # TODO HOLI-8088 remove test once update_authenticated_user is removed
    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("openbook_auth.schema.mutations.publish_user_name_updated_event")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_can_update_authenticated_user(
        self,
        mock_create_or_update_subscriber,
        mock_get_language_from_request,
        mock_publish_user_name_updated_event,
        mock_patch,
    ):
        response = self.create_response(200)
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

        request = HttpRequest()
        request.COOKIES = {}
        request.user = user

        executed = async_to_sync(schema.execute)(
            """
            mutation test($input: UpdateAuthenticatedUserInput!) {
                updateAuthenticatedUser(input: $input) {
                    id
                    pronouns
                    location
                    geolocationId
                    engagementLevel
                }
            }
            """,
            context_value=benedict({"request": request}),
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

        assert executed.errors is None

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
            timeout=30,
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
        assert persisted_profile.geolocation is not None
        assert geos.GEOSGeometry(json.dumps(geolocation_geometry)) == persisted_profile.geolocation

        mock_publish_user_name_updated_event.assert_called_once_with(user=user)
        mock_create_or_update_subscriber.assert_called_once_with(
            user=user, locale=mock_get_language_from_request.return_value
        )

    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("openbook_auth.schema.mutations.publish_user_name_updated_event")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_can_update_authenticated_user_v2(
        self,
        mock_create_or_update_subscriber,
        mock_get_language_from_request,
        mock_publish_user_name_updated_event,
        mock_patch,
    ):
        response = self.create_response(200)
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
        tracking_consent_analytics = True
        tracking_consent_personalization = False

        json_body = [
            {"op": "add", "path": "/traits/given_name", "value": f"{first_name}"},
            {"op": "add", "path": "/traits/family_name", "value": f"{last_name}"},
            {"op": "add", "path": "/traits/name", "value": f"{first_name} {last_name}"},
        ]

        request = HttpRequest()
        request.COOKIES = {}
        request.user = user

        executed = async_to_sync(schema.execute)(
            """
            mutation test($input: UpdateAuthenticatedUserInput!) {
                updateAuthenticatedUserV2(input: $input) {
                    id
                    pronouns
                    location
                    geolocationId
                    engagementLevel
                    trackingConsentAnalytics
                    trackingConsentPersonalization
                }
            }
            """,
            context_value=benedict({"request": request}),
            variable_values={
                "input": {
                    "pronouns": pronouns,
                    "firstName": first_name,
                    "lastName": last_name,
                    "location": location,
                    "geolocation": geolocation,
                    "engagementLevel": engagement_level,
                    "trackingConsentAnalytics": tracking_consent_analytics,
                    "trackingConsentPersonalization": tracking_consent_personalization,
                }
            },
        )

        assert executed.errors is None

        mock_patch.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=json_body,
            timeout=30,
        )
        updated_user = executed.data["updateAuthenticatedUserV2"]
        graphql_pronouns = updated_user["pronouns"]

        persisted_user = User.objects.get(username=user.username)

        assert tracking_consent_analytics == persisted_user.tracking_consent_analytics
        assert tracking_consent_personalization == persisted_user.tracking_consent_personalization
        assert graphql_pronouns == persisted_user.profile.pronouns
        assert graphql_pronouns == pronouns
        assert last_name == persisted_user.profile.last_name
        assert first_name == persisted_user.profile.name
        assert persisted_user.profile.engagement_level == EngagementLevelChoice.INITIATOR
        assert location == persisted_user.profile.location
        assert geolocation_id == persisted_user.profile.geolocation_id
        assert persisted_user.profile.geolocation is not None
        assert geos.GEOSGeometry(json.dumps(geolocation_geometry)) == persisted_user.profile.geolocation

        mock_publish_user_name_updated_event.assert_called_once_with(user=user)
        mock_create_or_update_subscriber.assert_called_once_with(
            user=user, locale=mock_get_language_from_request.return_value
        )

    @mock.patch("openbook_auth.tasks.requests.put")
    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_can_update_authenticated_user_generates_an_identity(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, ory_patch_mock, matrix_put_mock
    ):
        ory_patch_mock.return_value = self.create_response(200)
        matrix_put_mock.return_value = self.create_response(201)
        user = make_user()
        user.identity = None

        result = api_update_authenticated_user_names_data(user, "Fritz", "Meier")

        ory_patch_mock.assert_any_call(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=[{"op": "add", "path": "/metadata_public/identity", "value": "fritz.meier"}],
            timeout=30,
        )

        persisted_user = User.objects.get(username=user.username)

        assert "fritz.meier" == persisted_user.identity
        assert "fritz.meier" == result["identity"]

        # test it only registers identity once
        result = api_update_authenticated_user_names_data(user, "Hans", "Meier")

        persisted_user = User.objects.get(username=user.username)
        assert "fritz.meier" == persisted_user.identity
        assert "fritz.meier" == result["identity"]

        assert mock_create_or_update_subscriber.call_count == 2

    @mock.patch("openbook_auth.tasks.requests.put")
    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_api_registers_new_user_with_already_taken_identity_for_a_user(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, ory_patch_mock, matrix_put_mock
    ):
        ory_update_response_stub = self.create_response(200)
        ory_patch_mock.return_value = ory_update_response_stub
        matrix_put_mock.return_value = self.create_response(201)

        make_user(name="Fritz", last_name="Hansen", identity="fritz.hansen")
        new_fritz = make_user(name="Fritz", last_name="Hansen", identity="something_to_prevent_collision")
        new_fritz.identity = None

        result = api_update_authenticated_user_names_data(new_fritz, "Fritz", "Hansen")

        assert result["identity"] == "fritz.hansen1"

        expected_json_body = [{"op": "add", "path": "/metadata_public/identity", "value": "fritz.hansen1"}]

        ory_patch_mock.assert_any_call(
            f"{settings.ORY_BASE_URL}/admin/identities/{new_fritz.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
            json=expected_json_body,
            timeout=30,
        )

        mock_create_or_update_subscriber.assert_called_once_with(
            user=new_fritz, locale=mock_get_language_from_request.return_value
        )

    @mock.patch("openbook_auth.tasks.requests.put")
    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_api_registers_new_user_with_ory_failing_once(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, ory_patch_mock, matrix_put_mock
    ):
        ory_update_user_name_success = self.create_response(200)
        ory_update_identity_conflict = self.create_response(409, {"error": {"message": "Error Message"}})
        ory_update_identity_success = self.create_response(200)
        matrix_put_mock.return_value = self.create_response(201)

        ory_patch_mock.side_effect = [
            ory_update_identity_conflict,
            ory_update_identity_success,
            ory_update_user_name_success,
        ]

        new_user = make_user()
        new_user.identity = None

        result = api_update_authenticated_user_names_data(new_user, "Fritz", "Hansen")

        assert result["identity"] == "fritz.hansen"

        ory_patch_mock.assert_has_calls(
            [
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/metadata_public/identity", "value": "fritz.hansen"},
                    ],
                    timeout=30,
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/metadata_public/identity", "value": "fritz.hansen"},
                    ],
                    timeout=30,
                ),
            ]
        )

        mock_create_or_update_subscriber.assert_called_once_with(
            user=new_user, locale=mock_get_language_from_request.return_value
        )

    @mock.patch("openbook_auth.tasks.requests.put")
    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_api_registers_new_user_only_first_name_with_ory_failing_once(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, ory_patch_mock, matrix_put_mock
    ):
        ory_update_user_name_success = self.create_response(200)
        ory_update_identity_conflict = self.create_response(409, {"error": {"message": "Error Message"}})
        ory_update_identity_success = self.create_response(200)
        matrix_put_mock.return_value = self.create_response(201)

        ory_patch_mock.side_effect = [
            ory_update_identity_conflict,
            ory_update_identity_success,
            ory_update_user_name_success,
        ]

        new_user = make_user()
        new_user.identity = None

        result = api_update_authenticated_user_names_data(new_user, "Fritz", "")

        assert result["identity"] == "fritz"

        ory_patch_mock.assert_has_calls(
            [
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/metadata_public/identity", "value": "fritz"},
                    ],
                    timeout=30,
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/metadata_public/identity", "value": "fritz"},
                    ],
                    timeout=30,
                ),
            ]
        )

        mock_create_or_update_subscriber.assert_called_once_with(
            user=new_user, locale=mock_get_language_from_request.return_value
        )

    @mock.patch("openbook_auth.tasks.requests.put")
    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_api_registers_new_user_with_matrix_id_taken(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, ory_patch_mock, matrix_put_mock
    ):
        ory_update_user_name_success = self.create_response(200)
        ory_update_identity_success = self.create_response(200)

        ory_patch_mock.side_effect = [
            ory_update_identity_success,
            ory_update_user_name_success,
        ]

        matrix_put_mock.side_effect = [self.create_response(200), self.create_response(201)]

        new_user = make_user()
        new_user.identity = None

        result = api_update_authenticated_user_names_data(new_user, "Fritz", "Fratz")

        assert result["identity"] == "fritz.fratz1"

        mock_create_or_update_subscriber.assert_called_once_with(
            user=new_user, locale=mock_get_language_from_request.return_value
        )

    @mock.patch("openbook_auth.tasks.requests.put")
    @mock.patch("openbook_auth.tasks.requests.patch")
    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.create_or_update_subscriber")
    def test_api_registers_new_user_with_ory_failing_too_many_times(
        self, mock_create_or_update_subscriber, mock_get_language_from_request, ory_patch_mock, matrix_put_mock
    ):
        ory_update_user_name_success = self.create_response(200)
        ory_update_identity_conflict = self.create_response(409, {"error": {"message": "Error Message"}})
        matrix_put_mock.return_value = self.create_response(201)

        ory_patch_mock.side_effect = [
            ory_update_identity_conflict,
            ory_update_identity_conflict,
            ory_update_identity_conflict,
            ory_update_user_name_success,
        ]

        new_user = make_user()
        new_user.identity = None

        with capture_logs() as cap_logs:
            result = api_update_authenticated_user_names_data(new_user, "Fritz", "Hansen")
            log_entry = next(e for e in cap_logs if "MANUAL INTERVENTION NEEDED!" in e["event"])
            assert log_entry["log_level"] == "error"

        assert result["identity"] == "fritz.hansen"

        ory_patch_mock.assert_has_calls(
            [
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/metadata_public/identity", "value": "fritz.hansen"},
                    ],
                    timeout=30,
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/metadata_public/identity", "value": "fritz.hansen"},
                    ],
                    timeout=30,
                ),
                call(
                    f"{settings.ORY_BASE_URL}/admin/identities/{new_user.username}",
                    headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
                    json=[
                        {"op": "add", "path": "/metadata_public/identity", "value": "fritz.hansen"},
                    ],
                    timeout=30,
                ),
            ]
        )

        mock_create_or_update_subscriber.assert_called_once_with(
            user=new_user, locale=mock_get_language_from_request.return_value
        )

    @mock.patch("openbook_auth.tasks.requests.delete")
    @mock.patch("openbook_auth.schema.mutations.publish_user_deleted_event")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_subscriber")
    def test_can_delete_authenticated_user(self, mock_delete_subscriber, mock_publish_user_deleted_event, mock_delete):
        mock_delete.return_value = self.create_response(204)

        user = make_user(name="Fritz", last_name="Meier")

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
        mock_delete_subscriber.assert_called_once_with(user_id=str(user.username))

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_auth.tasks.requests.delete")
    @mock.patch("openbook_auth.schema.mutations.publish_user_deleted_event")
    @mock.patch("openbook_auth.schema.mutations.publish_space_deleted_event")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_can_delete_authenticated_user_and_pending_notifications(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_delete_subscriber,
        mock_publish_space_deleted_event,
        mock_publish_user_deleted_event,
        mock_delete,
        mock_send_space_membership_invite_notification,
        mock_send_space_membership_request_notification,
    ):
        mock_delete.return_value = self.create_response(204)

        user = make_user(name="Fritz", last_name="Meier")
        other_admin = make_user()
        invitee = make_user()
        administered_space = make_community(admins=[user, other_admin])
        space_for_join_request = make_community()
        space_for_invite = make_community()

        # Invite invitee to join administered_space
        mutate_update_space_user_connection_data(
            auth_user=user,
            space_id=administered_space.id,
            user_id=invitee.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        invite = administered_space.get_membership_invite(invitee)

        # Request to join space_for_join_request
        mutate_update_space_user_connection_data(
            auth_user=user,
            space_id=space_for_join_request.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        membership_request = space_for_join_request.get_membership_request(user)

        # Get invited to join space_for_invite
        mutate_update_space_user_connection_data(
            auth_user=space_for_invite.creator,
            space_id=space_for_invite.id,
            user_id=user.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        own_invite = space_for_invite.get_membership_invite(user)

        # WHEN
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

        # THEN
        mock_delete.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
        )

        assert mutation_response.data["deleteAuthenticatedUser"]["success"] is True

        mock_publish_user_deleted_event.assert_called_once_with(user=user)
        # Expect administered_space not to be deleted as there is a second admin
        mock_publish_space_deleted_event.assert_not_called()
        mock_delete_subscriber.assert_called_once_with(user_id=str(user.username))
        # Expect pending notifications for deleted user to be deleted resp. workflows to be cancelled - but not for invite of invitee
        mock_notification_api_cancel_workflow.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(own_invite.id))]
        )
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(own_invite.id))]
        )

    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_request_notification")
    @mock.patch("openbook_notifications.services.NotificationsService.send_space_membership_invite_notification")
    @mock.patch("openbook_auth.tasks.requests.delete")
    @mock.patch("openbook_auth.schema.mutations.publish_user_deleted_event")
    @mock.patch("openbook_auth.schema.mutations.publish_space_deleted_event")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.cancel_workflow")
    @mock.patch("openbook_notifications.api.NotificationApi.delete_in_app_messages")
    def test_can_delete_authenticated_user_with_spaces_and_notifications(
        self,
        mock_notification_api_delete_in_app_messages,
        mock_notification_api_cancel_workflow,
        mock_delete_subscriber,
        mock_publish_space_deleted_event,
        mock_publish_user_deleted_event,
        mock_delete,
        mock_send_space_membership_invite_notification,
        mock_send_space_membership_request_notification,
    ):
        mock_delete.return_value = self.create_response(204)

        user = make_user(name="Fritz", last_name="Meier")
        space = make_community(creator=user)
        invitee = make_user()
        membership_requestor = make_user()

        # Invite invitee to join space
        mutate_update_space_user_connection_data(
            auth_user=user,
            space_id=space.id,
            user_id=invitee.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_INVITEE,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        invite = space.get_membership_invite(invitee)

        # Receive request from membership_requestor to join space
        mutate_update_space_user_connection_data(
            auth_user=membership_requestor,
            space_id=space.id,
            connection_type=SpaceUserConnectionType.MEMBERSHIP_REQUESTOR,
            connect_action=UpdateConnectionAction.CONNECT,
        )
        membership_request = space.get_membership_request(membership_requestor)

        # WHEN
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

        # THEN
        mock_delete.assert_called_once_with(
            f"{settings.ORY_BASE_URL}/admin/identities/{user.username}",
            headers={"Authorization": f"Bearer {settings.ORY_ACCESS_TOKEN}"},
        )

        assert mutation_response.data["deleteAuthenticatedUser"]["success"] is True

        mock_publish_user_deleted_event.assert_called_once_with(user=user)
        # Expect space to be deleted as there are no other admins left
        mock_publish_space_deleted_event.assert_called_once_with(space)
        mock_delete_subscriber.assert_called_once_with(user_id=str(user.username))
        # Expect pending notifications for invitations and membership requests to be deleted resp. workflows to be cancelled
        mock_notification_api_cancel_workflow.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(invite.id))]
        )
        mock_notification_api_delete_in_app_messages.assert_has_calls(
            [mock.call(transaction_id=str(membership_request.id)), mock.call(transaction_id=str(invite.id))]
        )

    def create_response(self, http_status, json_body={}):
        response = Response()
        response.status_code = http_status
        response._content = str.encode(json.dumps(json_body))
        return response

    def test_block_user(self):
        blocking_user = make_user(name="BlockingUser")
        two_hours_ago = datetime.now() - timedelta(hours=2)
        blocked_user = make_user(name="BlockedUser", date_joined=two_hours_ago)
        other_user = make_user(name="OtherUser", date_joined=two_hours_ago)
        other_user.save()

        other_post = other_user.create_post(
            text=(make_fake_post_text()), title=(make_fake_post_title()), is_public=True
        )
        other_post.comment(text="comment text 1", commenter=blocked_user)

        blocked_post = blocked_user.create_post(
            text=(make_fake_post_text()), title=(make_fake_post_title()), is_public=True
        )
        blocked_post.comment(text="comment text 1", commenter=other_user)

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

        blocked_post_raw = get_post_with_id_raw(blocked_post.id, blocking_user)
        assert blocked_post_raw.data["postById"] is None
        other_post_data = get_post_with_id_data(other_post, blocking_user)
        assert other_post_data["involvedUsers"]["totalResults"] == 2  # does include blocked users
        assert len(other_post_data["involvedUsers"]["data"]) == 1  # does not include blocked users
        assert other_post_data["numberOfComments"] == 1  # does include blocked users
        assert len(other_post_data["comments"]) == 0  # does not include blocked users
        assert other_post_data["commenters"]["totalResults"] == 1  # does include blocked users
        assert len(other_post_data["commenters"]["data"]) == 0  # does not include blocked users

        assert response.errors is None
        assert response.data["blockUser"]["success"] is True

        response_after_blocking = get_user_with_id_raw(blocked_user, blocking_user)
        assert response_after_blocking.data["userById"] is None

        response_after_blocking = get_user_with_id_raw(blocking_user, blocked_user)
        assert response_after_blocking.data["userById"] is None

        response = async_to_sync(schema.execute)(
            """
            query {
                userSuggestions(limit:20) {
                    totalResults
                    data {
                        fullName
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": blocking_user}}),
        )
        assert response.data["userSuggestions"]["totalResults"] == 2  # does include blocked users
        assert len(response.data["userSuggestions"]["data"]) == 1  # does not include blocked users
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

    def mutate_register_device(self, user, token="some_token", device_type="ANDROID"):
        register_device_mutation = """
          mutation registerDevice($input: RegisterDeviceInput!) {
            registerDevice(input: $input) {
              success
            }
          }
        """

        request = HttpRequest()
        request.COOKIES = {}
        request.user = user

        return async_to_sync(schema.execute)(
            register_device_mutation,
            context_value=benedict({"request": request}),
            variable_values={"input": {"token": token, "deviceType": device_type}},
        )

    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.find_or_create_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.set_subscriber_credentials")
    def test_can_register_device(
        self, mock_set_subscriber_credentials, mock_find_or_create_subscriber, mock_get_language_from_request
    ):
        user = make_user()

        assert len(user.devices.all()) == 0

        response = self.mutate_register_device(user)

        assert response.errors is None
        assert response.data["registerDevice"]["success"] is True

        devices = user.devices.all()
        assert len(devices) == 1
        assert devices[0].token == "some_token"
        assert devices[0].device_type == "ANDROID"
        mock_set_subscriber_credentials.assert_called_once_with(
            subscriber_id=str(user.username), provider_id=NotificationProvider.FCM, device_tokens=["some_token"]
        )
        mock_find_or_create_subscriber.assert_called_once_with(user=user, locale="en")

    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.find_or_create_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.set_subscriber_credentials")
    def test_can_register_the_same_device_twice(
        self, mock_set_subscriber_credentials, mock_find_or_create_subscriber, mock_get_language_from_request
    ):
        # GIVEN all systems work fine
        user = make_user()

        # WHEN user tries to register their device
        response = self.mutate_register_device(user)

        # THEN the request succeeds
        assert response.errors is None
        assert response.data["registerDevice"]["success"] is True

        # THEN the device was registered in Okuna and in the notification system
        assert len(user.devices.all()) == 1
        mock_set_subscriber_credentials.assert_called_once_with(
            subscriber_id=str(user.username), provider_id=NotificationProvider.FCM, device_tokens=["some_token"]
        )

        # WHEN user "re-tries" to register their device (e.g. due to app restart)
        response = self.mutate_register_device(user)

        # THEN the request succeeds
        assert response.errors is None
        assert response.data["registerDevice"]["success"] is True

        # THEN the device is still known to Okuna
        assert len(user.devices.all()) == 1

        # THEN notification system has *still* only been called once (because device was already known)
        mock_set_subscriber_credentials.assert_called_once_with(
            subscriber_id=str(user.username), provider_id=NotificationProvider.FCM, device_tokens=["some_token"]
        )
        mock_find_or_create_subscriber.assert_called_once_with(user=user, locale="en")

    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.find_or_create_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.set_subscriber_credentials")
    def test_only_registers_device_in_okuna_if_succeeded_in_notification_system(
        self, mock_set_subscriber_credentials, mock_find_or_create_subscriber, mock_get_language_from_request
    ):
        # GIVEN registering a device in the notification system fails
        user = make_user()
        mock_set_subscriber_credentials.side_effect = Exception("Server error")

        # WHEN user tries to register their device
        response = self.mutate_register_device(user)

        # THEN the request fails
        assert response.errors is not None

        # THEN no device was registered in Okuna
        assert len(user.devices.all()) == 0

        # WHEN user retries to register their device
        mock_set_subscriber_credentials.side_effect = None
        mock_set_subscriber_credentials.reset_mock()
        response = self.mutate_register_device(user)

        # THEN the request succeeds
        assert response.errors is None
        assert response.data["registerDevice"]["success"] is True

        # THEN the device was registered in Okuna and in the notification system
        assert len(user.devices.all()) == 1
        mock_set_subscriber_credentials.assert_called_once_with(
            subscriber_id=str(user.username), provider_id=NotificationProvider.FCM, device_tokens=["some_token"]
        )
        mock_find_or_create_subscriber.assert_called()

    @mock.patch("django.utils.translation.get_language_from_request", return_value="en")
    @mock.patch("openbook_notifications.api.NotificationApi.find_or_create_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.set_subscriber_credentials")
    def test_only_registers_device_in_okuna_if_subscriber_creation_succeeded_in_notification_system(
        self, mock_set_subscriber_credentials, mock_find_or_create_subscriber, mock_get_language_from_request
    ):
        # GIVEN registering a device in the notification system fails
        user = make_user()
        mock_find_or_create_subscriber.side_effect = Exception("Server error")

        # WHEN user tries to register their device
        response = self.mutate_register_device(user)

        # THEN the request fails
        assert response.errors is not None

        # THEN no device was registered in Okuna
        assert len(user.devices.all()) == 0

        # WHEN user retries to register their device
        mock_find_or_create_subscriber.side_effect = None
        mock_find_or_create_subscriber.reset_mock()
        response = self.mutate_register_device(user)

        # THEN the request succeeds
        assert response.errors is None
        assert response.data["registerDevice"]["success"] is True

        # THEN the device was registered in Okuna and in the notification system
        assert len(user.devices.all()) == 1
        mock_set_subscriber_credentials.assert_called_once_with(
            subscriber_id=str(user.username), provider_id=NotificationProvider.FCM, device_tokens=["some_token"]
        )
        mock_find_or_create_subscriber.assert_called()

    @mock.patch("openbook_notifications.api.NotificationApi.find_or_create_subscriber")
    @mock.patch("openbook_notifications.api.NotificationApi.set_subscriber_credentials")
    def test_can_not_register_device_if_not_logged_in(
        self, mock_set_subscriber_credentials, mock_find_or_create_subscriber
    ):
        response = self.mutate_register_device(AnonymousUser)

        assert_is_unauthorized(response)
        mock_find_or_create_subscriber.assert_not_called()
        mock_set_subscriber_credentials.assert_not_called()

    def test_validates_device_registration(self):
        user = make_user()

        expected_errors = [
            {
                "field": "token",
                "value": None,
                "expected_error": "Expected non-nullable type",
            },
            {
                "field": "token",
                "value": "",
                "expected_code": "blank",
            },
            {
                "field": "token",
                "value": "f" * 300,
                "expected_code": "max_length",
            },
            {
                "field": "device_type",
                "value": None,
                "expected_error": "Expected non-nullable type",
            },
            {
                "field": "device_type",
                "value": "",
                "expected_error": "invalid value",
            },
            {
                "field": "device_type",
                "value": "FOOBAR",
                "expected_error": "invalid value",
            },
        ]

        for test_case in expected_errors:
            response = self.mutate_register_device(
                user,
                token=test_case["value"] if test_case["field"] == "token" else "some_token",
                device_type=test_case["value"] if test_case["field"] == "device_type" else "ANDROID",
            )
            if "expected_code" in test_case:
                field_errors = json.loads(response.errors[0].extensions["errors"])
                assert test_case["expected_code"] == field_errors[test_case["field"]][0]["code"]
            else:
                assert test_case["expected_error"] in str(response.errors[0].message)
            assert (response.data["registerDevice"] if response.data else response.data) is None

    def test_connected_users(self):
        user1 = make_user()
        user2 = make_user(name="B", last_name="B")
        user3 = make_user(name="A", last_name="A")

        # Setup full connections to user2 and user3
        connect_to_user(user1, user2)
        connect_to_user(user2, user1)
        connect_to_user(user1, user3)
        connect_to_user(user3, user1)

        connected_users = get_connected_users(user1)
        assert connected_users["totalResults"] == 2
        assert connected_users["data"][0]["id"] == str(user3.id)
        assert connected_users["data"][1]["id"] == str(user2.id)

    def test_cannot_retrieve_connected_users_if_not_logged_in(self):
        response = get_connected_users_raw()
        assert_is_unauthorized(response)

    def test_user_suggestions_only_accessible_when_logged_in(self):
        response = async_to_sync(schema.execute)(
            """
            query {
                userSuggestions {
                    totalResults
                    data {
                        id
                        fullName
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": AnonymousUser}}),
        )
        assert_is_unauthorized(response)

    def test_user_suggestions_limited(self):
        user = make_user()
        response = async_to_sync(schema.execute)(
            """
            query {
                userSuggestions(offset: 20) {
                    totalResults
                    data {
                        id
                        fullName
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": user}}),
        )
        assert_is_forbidden(response)

    def test_user_suggestions(self):
        user = make_user()
        for x in range(0, 25):
            make_user(name="A", last_name="B" + str(x), date_joined=datetime.now() - timedelta(hours=2))
        response = async_to_sync(schema.execute)(
            """
            query {
                userSuggestions {
                    totalResults
                    data {
                        id
                        fullName
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": user}}),
        )
        assert response.errors is None
        assert response.data["userSuggestions"]["totalResults"] == 25
        assert len(response.data["userSuggestions"]["data"]) == 10

        # A maximum of 20 user suggestions may be requested
        response = async_to_sync(schema.execute)(
            """
            query {
                userSuggestions(offset:15, limit: 25) {
                    totalResults
                    data {
                        id
                        fullName
                    }
                }
            }
            """,
            context_value=benedict({"request": {"user": user}}),
        )
        assert response.errors is None
        assert response.data["userSuggestions"]["totalResults"] == 25
        assert len(response.data["userSuggestions"]["data"]) == 5
