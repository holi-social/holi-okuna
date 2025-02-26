import uuid
from datetime import datetime, timedelta
from typing import Optional
from django.utils import timezone

import strawberry
import strawberry_django
from django.db.models import Q
from strawberry.types import Info

from openbook_auth.models import User as UserModel
from openbook_auth.models import UserBlock
from openbook_auth.schema.types import User
from openbook_common.schema.types import Paged
from openbook_insights.models import Discussion as DiscussionModel
from openbook_insights.models import Insight as InsightModel
from openbook_insights.schema.types import Insight
from openbook_insights.schema.types.discussion import Discussion
from openbook_insights.schema.types.insight import InsightPreview
from django.core.cache import cache


@strawberry.type
class Query:
    @strawberry_django.field()
    def insights_by_user_id(self, info: Info, id: uuid.UUID, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        current_user = info.context.request.user
        user = UserModel.objects.filter(UserModel.is_visible_ignore_blocked_query()).get(username=id)
        user = UserBlock.filter_single_object(current_user, user, lambda u: u.id)
        return Paged.of(
            InsightModel.objects.filter(creator=user).order_by("-date_published", "id"),
            offset,
            limit,
        )

    @strawberry_django.field()
    def last_insights(self, info, offset: int = 0, limit: int = 10) -> Paged[Insight]:
        current_user = info.context.request.user

        base_queryset = InsightModel.objects.filter(
            Q(creator__isnull=True) | UserModel.is_visible_ignore_blocked_query("creator"),
            date_published__lte=datetime.now(),
        ).select_related("creator", "creator__profile", "topic")

        base_queryset = base_queryset.prefetch_related("posts")

        base_queryset = base_queryset.order_by("-date_published", "id")

        paged_insights = UserBlock.paged(
            current_user,
            lambda insight: None if insight.creator is None else insight.creator.id,
            base_queryset,
            offset,
            limit,
        )

        return paged_insights

    @strawberry_django.field()
    def feed_insights(self, info, offset: int = 0, limit: int = 10) -> Paged[InsightPreview]:
        current_user = info.context.request.user

        # Generate cache key based on pagination
        cache_key = f"feed_insights:o{offset}:l{limit}"
        cached_insights = cache.get(cache_key)
        if cached_insights:
            return cached_insights

        base_queryset = InsightModel.objects.filter(
            Q(creator__isnull=True) | UserModel.is_visible_ignore_blocked_query("creator"),
            date_published__lte=datetime.now(),
        ).select_related("creator", "creator__profile")

        base_queryset = base_queryset.order_by("-date_published", "id")

        paged_insights = UserBlock.paged(
            current_user,
            lambda insight: None if insight.creator is None else insight.creator.id,
            base_queryset,
            offset,
            limit,
        )

        cache.set(cache_key, paged_insights)
        return paged_insights

    @strawberry_django.field()
    def insight_by_id(self, info, id: uuid.UUID) -> Optional[Insight]:
        current_user = info.context.request.user
        insight = (
            InsightModel.objects.filter(Q(creator__isnull=True) | UserModel.is_visible_ignore_blocked_query("creator"))
            .filter(date_published__lte=datetime.now())
            .get(id=id)
        )
        return UserBlock.filter_single_object(
            current_user,
            insight,
            lambda i: None if i.creator is None else i.creator.id,
        )

    @strawberry_django.field()
    def insight_authors(self, limit: int = 10, offset: int = 0) -> Paged[User]:
        return Paged.of(
            UserModel.objects.filter(curated_insights__isnull=False, profile__isnull=False)
            .order_by("profile__name", "profile__last_name")
            .distinct(),
            limit=limit,
            offset=offset,
        )

    @strawberry_django.field()
    def discussion_by_id(self, id: uuid.UUID) -> Discussion:
        return DiscussionModel.objects.get(pk=id)
