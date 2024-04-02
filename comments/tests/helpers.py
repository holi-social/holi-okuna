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


def add_reaction_to_comment(comment, posting_user):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CommentReactionInput!) {
            addReactionToComment(input: $input) {
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
            }
        },
    )


def remove_reaction_from_comment(comment, posting_user):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CommentReactionInput!) {
            removeReactionFromComment(input: $input) {
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
            }
        },
    )
