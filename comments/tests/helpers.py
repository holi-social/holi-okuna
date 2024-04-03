from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser

from openbook.graphql_schema import schema


def get_commenters(commentable_id, commentable_type, user=None):
    return async_to_sync(schema.execute)(
        """
        query test($commentable_id: UUID!, $commentable_type: CommentableType!) {
            commentable(id: $commentable_id, type: $commentable_type) {
                commenters{
                    totalResults
                    data {
                        firstName
                    }
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
        variable_values={"commentable_id": str(commentable_id), "commentable_type": commentable_type},
    )


def get_top_comment(commentable_id, commentable_type, user=None):
    return async_to_sync(schema.execute)(
        """
        query test($commentable_id: UUID!, $commentable_type: CommentableType!) {
            commentable(id: $commentable_id, type: $commentable_type) {
                topComment{
                    text
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
        variable_values={"commentable_id": str(commentable_id), "commentable_type": commentable_type},
    )


def add_comment(user, info):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreateCommentInput!){
            comments {
                add(input: $input) {
                    id
                    text
                }
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
            comments {
                delete(id: $id) {
                    success
                }
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
            comments {
                addReaction(input: $input) {
                    myReaction {
                        HEART
                    }
                    reactions {
                        HEART
                    }
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
            comments {
                removeReaction(input: $input) {
                    myReaction {
                        HEART
                    }
                    reactions {
                        HEART
                    }
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
