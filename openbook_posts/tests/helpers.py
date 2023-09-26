from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser

from openbook.graphql_schema import schema


def public_post_ids(posts_data):
    return [post_data["id"] for post_data in posts_data if post_data["isPublic"]]


def private_post_ids(posts_data):
    return [post_data["id"] for post_data in posts_data if not post_data["isPublic"]]


def get_post_with_id_data(post, user=None):
    response = get_post_with_id_raw(post, user)
    assert response.errors is None
    return response.data["postById"]


def get_post_with_id_raw(post, user=None):
    return async_to_sync(schema.execute)(
        f"""
        query {{
            postById(id: "{post.id}") {{
                id
                text
                title
                image {{
                    url
                    width
                    height
                }}
                created
                creator {{
                    id
                }}
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
                myReaction {{
                    HEART
                }}
                reactions {{
                    HEART
                }}
            }}
        }}
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
    )


def update_space_post(user, info):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: UpdatePostInput!){
            updateSpacePost(input: $input) {
                id
                title
                space {
                  id
                  posts {
                    totalResults
                  }
                }
                text
                isPublic
                created
                image {
                    url
                    blurhash
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": info},
    )


def create_space_post(user, info):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreatePostInput!){
            createSpacePost(input: $input) {
                id
                title
                posts {
                    totalResults
                    data {
                        title
                        text
                        isPublic
                        created
                    }
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": info},
    )


def create_space_post_2(user, info):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreatePostInput!){
            createSpacePost2(input: $input) {
                id
                title
                space {
                  id
                  posts {
                    totalResults
                    data {
                        title
                        text
                        isPublic
                        created
                        image {
                            url
                            blurhash
                        }
                    }
                  }
                }
                text
                isPublic
                created

            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": info},
    )


def update_space_post(user, info):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: UpdatePostInput!){
            updateSpacePost(input: $input) {
                id
                title
                space {
                  id
                  posts {
                    totalResults
                  }
                }
                text
                isPublic
                created
                image {
                    url
                    blurhash
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": info},
    )


def delete_post_comment(post_comment_id, user):
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


def delete_space_post(post_id, user):
    return async_to_sync(schema.execute)(
        """
            mutation Mutation($id: UUID!) {
                deleteSpacePost(id: $id) {
                    id
                    title
                    posts {
                        totalResults
                    }
                }
            }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "id": str(post_id),
        },
    )


def react_to_post(post, action, posting_user):
    return async_to_sync(schema.execute)(
        """
        mutation test($id: UUID!, $reactionType: ReactionType!, $reactionAction: ReactionAction!) {
            updatePostReaction(id: $id, reactionType: $reactionType, reactionAction: $reactionAction) {
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
            "id": str(post.id),
            "reactionType": "HEART",
            "reactionAction": action,
        },
    )


def react_to_post_comment(post_comment, action, posting_user):
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
