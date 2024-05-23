from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser

from openbook.graphql_schema import schema


def get_polls_with_id(poll, user=None):
    response = get_poll_with_id_raw(poll.id, user)
    assert response.errors is None
    return response.data["pollById"]


def get_poll_with_id_raw(poll_id, user=None):
    return async_to_sync(schema.execute)(
        f"""
        query {{
            pollById(id: "{poll_id}") {{
                choices {{
                    choiceText
                    id
                    votes
                }}
                created
                creator {{
                    id
                }}
                id
                isPublic
                modified
                questionText
            }}
        }}
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
    )


def create_poll(user, info):
    return async_to_sync(schema.execute)(
        """ 
        mutation test($input: CreatePollInput!){
            createPoll(input: $input) {
                created
                id
                isPublic
                modified
                questionText
                choices {
                    choiceText
                    id
                    votes
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": info},
    )


def update_votes(poll_id, user):
    return async_to_sync(schema.execute)(
        f"""
        mutation {{
            updateVotes(id:"{poll_id}") {{
                votes
                id
                choiceText
            }}
        }}
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
    )
