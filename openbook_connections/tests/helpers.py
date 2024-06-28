from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema
from openbook_communities.enums import UpdateConnectionAction


def disconnect_from_user(following_user, followed_user):
    return connect_user(following_user, followed_user, UpdateConnectionAction.DISCONNECT)


def connect_to_user(following_user, followed_user):
    return connect_user(following_user, followed_user, UpdateConnectionAction.CONNECT)


def connect_user(following_user, followed_user, action):
    connection_request_response = async_to_sync(schema.execute)(
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
        context_value=benedict({"request": {"user": following_user}}),
    )
    assert connection_request_response.errors is None
    return connection_request_response
