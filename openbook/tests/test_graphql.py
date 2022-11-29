import json
from typing import List

from benedict import BeneDict
from django.test import TestCase
from django.urls import reverse
from graphene.test import Client
from rest_framework import status

from openbook.graphql_schema import (
    schema,
    UpdateConnectionWithUserAction,
)
from openbook_auth.models import User, UserConnectionStatus
from openbook_common.tests.helpers import (
    make_user,
    make_authentication_headers_for_user,
)


class GraphQLTest(TestCase):
    def setUp(self):
        self.graphql = Client(schema)

    def test_query_http_api_query_authenticated_user(self):
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
            **headers
        )

        assert response.status_code == status.HTTP_200_OK

        authenticated_user = json.loads(response.content)["data"]["authenticatedUser"]
        assert authenticated_user["id"] == str(user.uuid)
        assert authenticated_user["fullName"] == user.profile.full_name()
        assert authenticated_user["engagementLevel"] == user.profile.engagement_level

    def test_get_user_by_name_returns_only_matching_user(self):
        expected_users = [
            make_user(name="Peter", last_name="Muster"),
            make_user(name="Petra", last_name="Rudtke"),
        ]
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
        assert_paged_results_equal(
            results=executed["data"]["userByName"],
            expected_data=[
                {"firstName": u.name, "lastName": u.last_name} for u in expected_users
            ],
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

        first_request_query = self.graphql.execute(
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
            first_request_query["data"]["updateConnectionWithUser"]["id"]
            == second_user.username
        )

        assert second_user.is_pending_confirm_connection_for_user_with_id(first_user.pk)
        assert (
            first_user.get_connection_status_with_user_id(second_user.pk)
            == UserConnectionStatus.REQUESTED
        )

        confirm_query = self.graphql.execute(
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
            confirm_query["data"]["updateConnectionWithUser"]["id"]
            == first_user.username
        )
        assert first_user.is_fully_connected_with_user_with_id(second_user.pk)
        assert second_user.is_fully_connected_with_user_with_id(first_user.pk)


def assert_paged_results_equal(results: dict, expected_data: List[dict[str, any]]):
    assert results["totalResults"] == len(expected_data)

    for el in expected_data:
        assert el in results["data"]
