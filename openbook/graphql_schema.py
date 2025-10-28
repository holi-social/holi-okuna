from typing import List, Optional

import strawberry
import structlog
from graphql import GraphQLError
from strawberry.tools import merge_types
from strawberry.types import ExecutionContext
from strawberry_django.optimizer import DjangoOptimizerExtension
from strawberry.extensions.query_depth_limiter import QueryDepthLimiter
from openbook import settings

from comments.schema import mutations as comments_mutations
from comments.schema import queries as comments_queries
from favorites.schema import mutations as favorites_mutations
from favorites.schema import queries as favorites_queries
from openbook.graphql_errors import GraphQLErrorCodes
from openbook.middleware.graphql_error_extension import GraphQLErrorExtension
from openbook_appointments.schema import mutations as appointments_mutations
from openbook_appointments.schema import queries as appointments_queries
from anon_stats.schema import mutations as anon_stats
from openbook_auth.schema import mutations as auth_mutations
from openbook_auth.schema import queries as auth_queries
from openbook_auth.utils import verify_authorized_user
from openbook_common.schema import queries as commons_queries
from openbook_communities.schema import mutations as communities_mutations
from openbook_communities.schema import queries as communities_queries
from openbook_connections.schema import mutations as connections_mutations
from openbook_insights.schema import mutations as insights_mutations
from openbook_insights.schema import queries as insights_queries
from openbook_moderation.schema import mutations as moderation_mutations
from openbook_notifications.schema import mutations as notifications_mutations
from openbook_notifications.schema import queries as notifications_queries
from openbook_posts.schema import mutations as posts_mutations
from openbook_posts.schema import queries as posts_queries
from openbook_polls.schema import mutations as polls_mutations
from openbook_polls.schema import queries as polls_queries
from openbook_terms.schema import queries as terms_queries
from feed_posts.schema import mutations as feed_posts_mutations
from feed_posts.schema import queries as feed_posts_queries
from openbook.storage_imagekit_io import ImagekitIoStorage
from feed_posts.schema import feed_queries
from volunteering.schema import queries as volunteering_queries
from volunteering.schema import mutations as volunteering_mutations

logger = structlog.get_logger(__name__)


class HoliSchema(strawberry.Schema):
    def process_errors(
        self,
        errors: List[GraphQLError],
        execution_context: Optional[ExecutionContext] = None,
    ) -> None:
        real_errors = [
            error
            for error in errors
            if not (
                error.extensions
                and "code" in error.extensions
                and error.extensions["code"]
                in [
                    GraphQLErrorCodes.BAD_USER_INPUT,
                    GraphQLErrorCodes.NOT_FOUND,
                    GraphQLErrorCodes.FORBIDDEN,
                    GraphQLErrorCodes.UNAUTHORIZED,
                ]
            )
            and not (
                # don't error log UUID parsing failures of user parameters (-> BAD_USER_INPUT)
                error.message.startswith("Value cannot represent a UUID:")
            )
        ]
        super().process_errors(real_errors, execution_context)


Query = merge_types(
    "Query",
    (
        auth_queries.Query,
        posts_queries.Query,
        polls_queries.Query,
        communities_queries.Query,
        terms_queries.Query,
        insights_queries.Query,
        notifications_queries.Query,
        commons_queries.Query,
        appointments_queries.Query,
        favorites_queries.Query,
        comments_queries.Query,
        feed_posts_queries.Query,
        feed_queries.Query,
        volunteering_queries.Query,
    ),
)


@strawberry.type
class ImageKitAuthParams:
    token: str
    signature: str
    expire: str
    public_key: str


@strawberry.type
class ImageKitMutations:
    @strawberry.mutation
    def get_imagekit_auth_params(self, info) -> ImageKitAuthParams:
        verify_authorized_user(info)
        storage = ImagekitIoStorage()
        auth_params = storage.get_imagekit_auth_params()

        return ImageKitAuthParams(
            token=auth_params["token"],
            signature=auth_params["signature"],
            expire=auth_params["expire"],
            public_key=settings.IMAGEKIT_PUBLIC_KEY,
        )


Mutation = merge_types(
    "Mutation",
    (
        anon_stats.Mutation,
        auth_mutations.Mutation,
        connections_mutations.Mutation,
        posts_mutations.Mutation,
        polls_mutations.Mutation,
        communities_mutations.Mutation,
        notifications_mutations.Mutation,
        moderation_mutations.Mutation,
        appointments_mutations.Mutation,
        insights_mutations.Mutation,
        favorites_mutations.Mutation,
        comments_mutations.Mutation,
        feed_posts_mutations.Mutation,
        volunteering_mutations.Mutation,
        ImageKitMutations,
    ),
)

schema = HoliSchema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension,
        GraphQLErrorExtension,
        QueryDepthLimiter(max_depth=6),
    ],
)
