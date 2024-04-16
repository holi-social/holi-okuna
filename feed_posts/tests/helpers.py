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
