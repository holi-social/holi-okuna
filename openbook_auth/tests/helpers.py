from typing import List

from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest

from openbook.graphql_schema import schema


def get_user_with_id_data(user_to_get, calling_user=None):
    response = get_user_with_id_raw(user_to_get, calling_user)
    assert response.errors is None
    return response.data["userById"]


def get_user_with_id_raw(user_to_get, calling_user=None):
    return async_to_sync(schema.execute)(
        f"""
        query {{
            userById(id: "{user_to_get.username}") {{
                id
            }}
        }}
        """,
        context_value=benedict({"request": {"user": calling_user or AnonymousUser}}),
    )


def get_users_by_chat_identities(user: User, identities: List[str]):
    response = async_to_sync(schema.execute)(
        """
        query($identities: [String!]!) {
            usersByChatIdentities(identities: $identities) {
                totalResults
                data {
                    id
                    firstName
                    lastName
                    avatar
                }
            }
        }
        """,
        variable_values={
            "identities": identities,
        },
        context_value=benedict({"request": {"user": user}}),
    )

    return response


def api_update_authenticated_user_names_data(user, first_name, last_name):
    request = HttpRequest()
    request.COOKIES = {}
    request.user = user
    response = async_to_sync(schema.execute)(
        """
        mutation test($input: UpdateAuthenticatedUserInput!) {
            updateAuthenticatedUserV2(input: $input) {
                id
                firstName
                lastName
                identity
            }
        }
        """,
        context_value=benedict({"request": request}),
        variable_values={"input": {"firstName": first_name, "lastName": last_name}},
    )
    assert response.errors is None
    return response.data["updateAuthenticatedUserV2"]


def get_user_connection_status_to_space_data(user_to_get, space, calling_user=None):
    response = get_user_connection_status_to_space_raw(user_to_get, space, calling_user)
    assert response.errors is None
    return response.data["userById"]["connectionStatusToSpace"]


def get_user_connection_status_to_space_raw(user_to_get, space, calling_user=None):
    return async_to_sync(schema.execute)(
        f"""
        query {{
            userById(id: "{user_to_get.username}") {{
                connectionStatusToSpace(spaceId: "{space.id}")
            }}
        }}
        """,
        context_value=benedict({"request": {"user": calling_user or AnonymousUser}}),
    )


def get_connected_users(calling_user=None):
    response = get_connected_users_raw(calling_user)
    assert response.errors is None
    return response.data["connectedUsers"]


def get_connected_users_raw(calling_user=None):
    return async_to_sync(schema.execute)(
        """
        query {
            connectedUsers {
                totalResults
                data {
                    id
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": calling_user or AnonymousUser}}),
    )
