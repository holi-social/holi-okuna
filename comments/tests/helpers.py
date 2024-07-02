from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser

from openbook.graphql_schema import schema


def get_comment_by_id(id, user=None):
    return async_to_sync(schema.execute)(
        """
        query GetComment($id: UUID!) {
            commentById(id: $id) {
                id
            }
        }
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
        variable_values={"id": str(id)},
    )


def get_comments(commentable_id, commentable_type, user=None, parent_comment_id=None):
    return async_to_sync(schema.execute)(
        """
        query test($commentable_id: UUID!, $commentable_type: CommentableType!) {
            commentable(id: $commentable_id, type: $commentable_type) {
                comments{
                    totalResults
                    data {
                        text
                        totalReplies
                        replies {
                            id
                        }
                    }
                }
                totalComments
            }
        }
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
        variable_values={"commentable_id": str(commentable_id), "commentable_type": commentable_type},
    )


def get_comments_with_parent_comment_id(commentable_id, commentable_type, user=None, parent_comment_id=None):
    return async_to_sync(schema.execute)(
        """
        query test($commentable_id: UUID!, $commentable_type: CommentableType!, $parent_comment_id: UUID) {
            commentable(id: $commentable_id, type: $commentable_type) {
                comments(parentCommentId: $parent_comment_id){
                    totalResults
                    data {
                        text
                    }
                }
            totalComments
            }
        }
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
        variable_values={
            "commentable_id": str(commentable_id),
            "commentable_type": commentable_type,
            "parent_comment_id": str(parent_comment_id) or None,
        },
    )


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
                totalComments
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


def add_reaction_to_comment(comment, reaction_type, posting_user):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CommentReactionInput!) {
            addReactionToComment(input: $input) {
                myReaction {
                    LOVE
                    SUPPORT
                    HOPE
                    CELEBRATE
                    INSIGHT
                    SUCCESS
                }
                reactions {
                    LOVE
                    SUPPORT
                    HOPE
                    CELEBRATE
                    INSIGHT
                    SUCCESS
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": posting_user}}),
        variable_values={
            "input": {
                "commentId": str(comment.id),
                "reactionType": reaction_type,
            }
        },
    )


def remove_reaction_from_comment(comment, reaction_type, posting_user):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CommentReactionInput!) {
            removeReactionFromComment(input: $input) {
                myReaction {
                    LOVE
                    SUPPORT
                    HOPE
                    CELEBRATE
                    INSIGHT
                    SUCCESS
                }
                reactions {
                    LOVE
                    SUPPORT
                    HOPE
                    CELEBRATE
                    INSIGHT
                    SUCCESS
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": posting_user}}),
        variable_values={
            "input": {
                "commentId": str(comment.id),
                "reactionType": reaction_type,
            }
        },
    )
