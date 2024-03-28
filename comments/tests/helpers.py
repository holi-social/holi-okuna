from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser

from openbook.graphql_schema import schema


def add_comment(user, info):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreateCommentInput!){
            addComment(input: $input) {
                id
                text
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": info},
    )


def get_post(post, user=None):
    response = get_post_with_id_raw(post.id, user)
    assert response.errors is None
    return response.data["postById"]


def get_post_with_id_raw(post_id, user=None):
    return async_to_sync(schema.execute)(
        f"""
        query {{
            postById(id: "{post_id}") {{
                comments {{
                    text
                    mentions {{
                        fullName
                    }}
                    myReaction {{
                        HEART
                    }}
                    reactions {{
                        HEART
                    }}
                }}
                mentions {{
                    fullName
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
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
    )


def delete_comment(post_comment_id, user):
    return async_to_sync(schema.execute)(
        """
        mutation test($id: UUID!) {
            deletePostComment(id: $id) {
                success
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "id": str(post_comment_id),
        },
    )


def react_to_comment(post_comment, action, posting_user):
    return async_to_sync(schema.execute)(
        """
        mutation test($id: UUID!, $reactionType: ReactionType!, $reactionAction: ReactionAction!) {
            updatePostCommentReaction(id: $id, reactionType: $reactionType, reactionAction: $reactionAction) {
                myReaction {
                    HEART
                }
                reactions {
                    HEART
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": posting_user}}),
        variable_values={
            "id": str(post_comment.id),
            "reactionType": "HEART",
            "reactionAction": action,
        },
    )
