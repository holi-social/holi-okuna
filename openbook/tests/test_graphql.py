from django.test import TestCase
from graphene.test import Client
from openbook.graphql_schema import schema


class GraphQLTest(TestCase):
    def setUp(self):
        self.client = Client(schema)

    def test_get_users_by_name_without_users_gives_empty_result(self):
        executed = self.client.execute(
            """
            query {
                userByName(substring: "a") {
                    totalResults
                    data {
                        id
                        fullName
                        firstName
                        lastName 
                    }
                }
            }
            """
        )
        assert executed == {"data": {"userByName": {"totalResults": 0, "data": []}}}
