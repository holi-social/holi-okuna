from asgiref.sync import async_to_sync
from benedict import benedict

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


def delete_comment(user, comment_id):
    return async_to_sync(schema.execute)(
        """
        mutation test($id: UUID!) {
            deleteComment(id: $id) {
                success
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "id": str(comment_id),
        },
    )


def react_to_comment(comment, action, posting_user):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CommentReactionInput!) {
            reactToComment(input: $input) {
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
            "input": {
                "commentId": str(comment.id),
                "reactionType": "HEART",
                "reactionAction": action,
            }
        },
    )
