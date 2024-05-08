from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser

from openbook.graphql_schema import schema


def get_polls_with_id(poll, user=None):
    response = get_poll_with_id_raw(poll.id, user)
    assert response.errors is None
    return response.data["pollById"]


def get_poll_with_id_raw(question_id, user=None):
    return async_to_sync(schema.execute)(
        f"""
        query {{
            pollById(id: "{question_id}") {{
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
