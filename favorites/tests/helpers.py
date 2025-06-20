from asgiref.sync import async_to_sync
from benedict import benedict
from django.contrib.auth.models import AnonymousUser

from openbook.graphql_schema import schema


def favorite(user, favoritable_id, favoritable_type):
    return async_to_sync(schema.execute)(
        """
        mutation Favorite($favoritableId: String!, $favoritableType: FavoritableType!) {
            favoriteV2(
                favoritableId: $favoritableId,
                favoritableType: $favoritableType
            ) {
                success
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "favoritableId": str(favoritable_id),
            "favoritableType": favoritable_type,
        },
    )


def unfavorite(user, favoritable_id, favoritable_type):
    return async_to_sync(schema.execute)(
        """
        mutation Unfavorite($favoritableId: String!, $favoritableType: FavoritableType!) {
            unfavoriteV2(
                favoritableId: $favoritableId,
                favoritableType: $favoritableType
            ) {
                success
            }
        }
        """,
        context_value=benedict({"request": {"user": user}}),
        variable_values={
            "favoritableId": str(favoritable_id),
            "favoritableType": favoritable_type,
        },
    )


def query_favorites(user, offset=0, limit=10):
    return async_to_sync(schema.execute)(
        """
        query GetFavorites($offset: Int!, $limit: Int!) {
            favorites(
               offset: $offset,
               limit: $limit
            ) {
                data {
                    id
                    favoritableId
                    favoritableType
                    favoritable {
                        ... on Insight {
                            __typename
                            id
                            title
                            description
                        }

                        ... on ExternalVolunteeringOpportunity {
                            __typename
                            externalId
                        }

                        ... on Task {
                            __typename
                            id
                            name
                            description
                        }
                    }
                }
            }
        }
        """,
        context_value=benedict({"request": {"user": user or AnonymousUser}}),
        variable_values={
            "offset": offset,
            "limit": limit,
        },
    )
