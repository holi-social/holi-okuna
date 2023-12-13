from typing import List, Optional

import strawberry
import structlog
from graphql import GraphQLError
from strawberry.tools import merge_types
from strawberry.types import ExecutionContext
from strawberry_django.optimizer import DjangoOptimizerExtension

from openbook.middleware.graphql_error_extension import GraphQLErrorExtension
from openbook.settings.sentry_config import HoliSentryTracingExtension
from openbook_auth.schema import mutations as auth_mutations
from openbook_auth.schema import queries as auth_queries
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.schema import queries as commons_queries
from openbook_communities.schema import mutations as communities_mutations
from openbook_communities.schema import queries as communities_queries
from openbook_connections.schema import mutations as connections_mutations
from openbook_insights.schema import queries as insights_queries
from openbook_moderation.schema import mutations as moderation_mutations
from openbook_notifications.schema import mutations as notifications_mutations
from openbook_notifications.schema import queries as notifications_queries
from openbook_posts.schema import mutations as posts_mutations
from openbook_posts.schema import queries as posts_queries
from openbook_terms.schema import queries as terms_queries
from openbook_appointments.schema import mutations as appointments_mutations

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
        ]
        super().process_errors(real_errors, execution_context)


Query = merge_types(
    "Query",
    (
        auth_queries.Query,
        posts_queries.Query,
        communities_queries.Query,
        terms_queries.Query,
        insights_queries.Query,
        notifications_queries.Query,
        commons_queries.Query,
    ),
)

Mutation = merge_types(
    "Mutation",
    (
        auth_mutations.Mutation,
        connections_mutations.Mutation,
        posts_mutations.Mutation,
        communities_mutations.Mutation,
        notifications_mutations.Mutation,
        moderation_mutations.Mutation,
        appointments_mutations.Mutation,
    ),
)


schema = HoliSchema(
    query=Query,
    mutation=Mutation,
    extensions=[
        DjangoOptimizerExtension,
        GraphQLErrorExtension,
        HoliSentryTracingExtension,
    ],
)
