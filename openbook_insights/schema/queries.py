import uuid
from datetime import datetime
from typing import Optional

import strawberry
import strawberry_django
from asgiref.sync import sync_to_async
from django.db.models import Q
from graphql import GraphQLError

from openbook_auth.models import User as UserModel, UserBlock
from openbook.graphql_errors import GraphQLErrorCodes
from openbook_common.schema.types import Paged
from openbook_insights.models import Insight as InsightModel
from openbook_insights.schema.types import Insight


@strawberry.type
class Query:
    @strawberry_django.field()
    def insights_by_user_id(self, info, id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        current_user = info.context.request.user
        try:
            user = UserModel.objects.filter(UserModel.is_visible_ignore_blocked_query()).get(username=id)
            user = UserBlock.filter_single_object(current_user, user, lambda u: u.id)
        except UserModel.DoesNotExist:
            raise GraphQLError("User not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
        return Paged.of(
            InsightModel.objects.filter(creator=user).order_by("-date_published", "id"),
            offset,
            limit,
        )

    @strawberry_django.field()
    def last_insights(self, info, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        current_user = info.context.request.user
        paged_insights = UserBlock.paged(
            current_user,
            lambda insight: None if insight.creator is None else insight.creator.id,
            InsightModel.objects.filter(
                Q(creator__isnull=True) | UserModel.is_visible_ignore_blocked_query("creator"),
                date_published__lte=datetime.now(),
            )
            .select_related("creator", "creator__profile", "topic")
            .prefetch_related(
                "posts",
                "posts__creator",
                "posts__comments__commenter",
            )
            .order_by("-date_published", "id")
            .cache(ops=["fetch", "count"], timeout=300),
            offset,
            limit,
        )

        return paged_insights

    @strawberry_django.field()
    def insight_by_id(self, info, id: uuid.UUID) -> Optional[Insight]:
        current_user = info.context.request.user
        try:
            insight = (
                InsightModel.objects.filter(
                    Q(creator__isnull=True) | UserModel.is_visible_ignore_blocked_query("creator")
                )
                .filter(date_published__lte=datetime.now())
                .get(id=id)
            )
            return UserBlock.filter_single_object(
                current_user,
                insight,
                lambda i: None if i.creator is None else i.creator.id,
            )
        except InsightModel.DoesNotExist:
            raise GraphQLError("Insight not found", extensions={"code": GraphQLErrorCodes.NOT_FOUND})
