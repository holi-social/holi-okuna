from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema


def create_feed_post(user, input):
    return async_to_sync(schema.execute)(
        """
        mutation test($input: CreateFeedPostInput!){
            createFeedPost(input: $input) {
                id
                title
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
        variable_values={"input": input},
    )


def my_posts(user):
    return async_to_sync(schema.execute)(
        """
        query {
            myPosts {
               totalResults
               data {
                    id
                    title
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
