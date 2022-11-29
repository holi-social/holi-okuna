import json
from typing import List

from django.test import TestCase
from django.urls import reverse
from graphene.test import Client
from rest_framework import status

from openbook.graphql_schema import schema, Paged
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
                    id,
                    fullName,
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


def assert_paged_results_equal(results: dict, expected_data: List[dict[str, any]]):
    assert results["totalResults"] == len(expected_data)

    for el in expected_data:
        assert el in results["data"]
