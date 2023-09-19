from asgiref.sync import async_to_sync
from benedict import benedict

from openbook.graphql_schema import schema


def get_notifications(user):
    response = async_to_sync(schema.execute)(
        """
        query {
            notifications {
                totalResults
                data {
                    id
                    owner {
                        fullName
                    }
                    created
                    read
                    notificationType
                    options {
                        user {
                            fullName
                        }
                        post {
                            title
                        }
                        postComment {
                            text
                        }
                        space {
                            title
                        }
                        teaser
                        message
                    }
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
    )
    assert response.errors is None
    return response.data["notifications"]


def has_new_notifications(followed_user):
    response = async_to_sync(schema.execute)(
        """
        query {
            hasNewNotifications {
                status
            }
        }
        """,
        context_value=benedict({"request": {"user": followed_user}}),
    )
    assert response.errors is None
    data = response.data["hasNewNotifications"]
    return data
