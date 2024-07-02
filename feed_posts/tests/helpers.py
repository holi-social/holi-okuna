from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema


# Mutations
def create_feed_post(user, input):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreateFeedPostInput!){
            createFeedPost(input: $input) {
                id
                title
                slug
                description
                visibility
                image
                imageBlurhash
                category {
                    id
                }
                topics {
                    id
                }
                creator {
                    id
                }
                mentions {
                    id
                    fullName
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": input},
    )


def update_feed_post(user, input):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: UpdateFeedPostInput!){
            updateFeedPost(input: $input) {
                id
                title
                slug
                description
                visibility
                image
                imageBlurhash
                category {
                    id
                }
                topics {
                    id
                }
                creator {
                    id
                }
                mentions {
                    id
                    fullName
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"input": input},
    )


def delete_feed_post(user, post_id):
    return async_to_sync(schema.execute)(
        """
        mutation test($postId: UUID!){
            deleteFeedPost(postId: $postId) {
                success        
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"postId": post_id},
    )


def update_feed_post_reaction(
    user,
    post_id,
    reaction_type,
    reaction_action,
):
    return async_to_sync(schema.execute)(
        """
        mutation test($postId: UUID!, $reactionType: ReactionType!, $reactionAction: ReactionAction!){
            updateFeedPostReaction(postId: $postId, reactionType: $reactionType, reactionAction: $reactionAction) {
                id
                title
                slug
                description
                visibility
                image
                imageBlurhash
                category {
                    id
                }
                topics {
                    id
                }
                creator {
                    id
                }
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
        context_value=benedict({"request": {"user": user}}),
        variable_values={"postId": post_id, "reactionType": reaction_type, "reactionAction": reaction_action},
    )


# Queries
def my_posts(user):
    return async_to_sync(schema.execute)(
        """
        query {
            myPosts {
               totalResults
               data {
                    id
                    title
                    slug
                    description
                    visibility
                    image
                    imageBlurhash
                    category {
                        id
                    }
                    topics {
                        id
                    }
                    creator {
                        id
                    }
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
    )


def posts_by_user_id(user, user_id):
    return async_to_sync(schema.execute)(
        """
        query ($userId: UUID!){
            postsByUserId(userId: $userId){
               totalResults
               data {
                    id
                    title
                    slug
                    description
                    visibility
                    image
                    imageBlurhash
                    category {
                        id
                    }
                    topics {
                        id
                    }
                    creator {
                        id
                    }
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"userId": str(user_id)},
    )


def feed_posts(user):
    return async_to_sync(schema.execute)(
        """
        query{
            feedPosts{
               totalResults
               data {
                    id
                    title
                    slug
                    description
                    visibility
                    image
                    imageBlurhash
                    category {
                        id
                    }
                    topics {
                        id
                    }
                    creator {
                        id
                    }
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
    )


def post(user, id_or_slug):
    return async_to_sync(schema.execute)(
        """
        query ($idOrSlug: String!){
            post(idOrSlug: $idOrSlug){
                    id
                    title
                    slug
                    description
                    visibility
                    image
                    imageBlurhash
                    category {
                        id
                    }
                    topics {
                        id
                    }
                    creator {
                        id
                    }
                }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={"idOrSlug": id_or_slug},
    )


# Helpers
def update_input_data(post_id, input_data):
    data = input_data.copy()
    data["postId"] = post_id
    return data
