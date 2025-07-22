import logging
import uuid
from typing import List, Optional

import strawberry
import strawberry_django
from django.db.models import Q

from comments.models import Comment as CommentModel
from favorites.models import UserFavorite
from openbook_auth.models import User as UserModel
from openbook_auth.models import UserBlock
from openbook_auth.schema.types import User
from openbook_common.schema.types import Paged
from openbook_insights.models import Insight as InsightModel
from openbook_insights.schema.types.discussion import Discussion
from openbook_insights.schema.types.initiative import Initiative
from openbook_insights.schema.types.quote import Quote
from openbook_insights.schema.types.recommendation import Recommendation
from openbook_posts.models import Post as PostModel
from openbook_posts.schema.types import Post
from openbook_terms.schema.types import Topic
from openbook_polls.models import Poll as PollModel
from openbook_polls.schema.types import Poll

logger = logging.getLogger(__name__)


@strawberry_django.type(InsightModel)
class Insight:
    id: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto
    creator: User = strawberry_django.field(select_related=["creator__profile"])
    date_published: strawberry.auto
    header_image: Optional[str]
    header_image_blurhash: Optional[str]
    topic: Optional[Topic] = strawberry_django.field(
        deprecation_reason="Deprecated since version 1.52, use topic_v2 instead.", default=None
    )
    topic_v2: Optional[str] = None

    @strawberry_django.field()
    def posts(self, info) -> List[Post]:
        current_user = info.context.request.user
        return UserBlock.filter_blocked_objects(
            current_user,
            lambda post: None if post.creator is None else post.creator.id,
            self.posts.filter(PostModel.is_visible_query(current_user)).distinct().order_by("created"),
        )

    # this should be removed and be replaced by paged posts
    @strawberry_django.field()
    def number_of_posts(self, info) -> int:
        current_user = info.context.request.user
        return self.posts.filter(PostModel.is_visible_query(current_user)).distinct().count()

    @strawberry_django.field()
    def polls(self, info) -> List[Poll]:
        current_user = info.context.request.user
        return UserBlock.filter_blocked_objects(
            current_user,
            lambda polls: None if polls.creator is None else polls.creator.id,
            self.polls.filter(PollModel.is_visible_query(current_user)).distinct().order_by("created"),
        )

    @strawberry_django.field(
        description="A list of all users involved interacting with the insight (excluding the insight creator). Includes authors of all the posts and all commenters of any posts and discussions"
    )
    def involved_users(self, info, offset: int = 0, limit: int = 3) -> Paged[User]:
        current_user = info.context.request.user
        query = UserModel.objects.filter(
            Q(
                (Q(posts__insights=self) & PostModel.is_visible_query(current_user, "posts"))
                | (Q(comments__post__insights=self) & CommentModel.is_visible_query(current_user, "comments"))
                | (
                    Q(comments__commentable_id__in=self.discussions.values_list("id", flat=True))
                    & CommentModel.is_visible_query(current_user, "comments")
                )
            ),
            is_deleted=False,
        ).distinct()
        query = query.select_related("profile").cache(ops=["fetch", "count"], timeout=300)
        return UserBlock.paged(current_user, lambda user: user.id, query, offset, limit)

    @strawberry_django.field()
    def recommendations(self) -> list[Recommendation]:
        return self.recommendations.all()

    @strawberry_django.field()
    def quotes(self) -> list[Quote]:
        return self.quotes.all()

    @strawberry_django.field()
    def is_favorite(self, info) -> bool:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return False

        return UserFavorite.objects.filter(user=current_user, favoritable_id=self.id).exists()

    @strawberry_django.field()
    def initiatives(self) -> list[Initiative]:
        return self.initiatives.all()

    @strawberry_django.field()
    def discussions(self) -> list[Discussion]:
        return self.discussions.all()

    @strawberry_django.field()
    def quote(self, id: uuid.UUID) -> Quote:
        return self.quotes.get(id=id)

    @strawberry_django.field()
    def recommendation(self, id: uuid.UUID) -> Recommendation:
        return self.recommendations.get(id=id)

    @strawberry_django.field()
    def initiative(self, id: uuid.UUID) -> Initiative:
        return self.initiatives.get(id=id)


@strawberry_django.type(InsightModel)
class InsightPreview:
    id: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto
    creator: Optional[User] = strawberry_django.field(select_related=["creator__profile"])
    date_published: strawberry.auto
    header_image: Optional[str]
    header_image_blurhash: Optional[str]
