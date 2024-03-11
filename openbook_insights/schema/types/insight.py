import logging
import uuid
from typing import Annotated, List, Optional

import strawberry
import strawberry_django
from django.db.models import Q

from openbook_auth.models import User as UserModel, UserBlock
from openbook_auth.schema.types import User
from openbook_common.schema.types import Paged
from openbook_insights.models import Insight as InsightModel, Quote as QuoteModel
from openbook_insights.schema.types.quote import Quote
from openbook_insights.schema.types.recommendation import Recommendation
from openbook_posts.models import Post as PostModel
from openbook_posts.models import PostComment as PostCommentModel
from openbook_terms.schema.types import Topic

logger = logging.getLogger(__name__)


@strawberry_django.type(InsightModel)
class Insight:
    id: strawberry.auto
    title: strawberry.auto
    description: strawberry.auto
    creator: Optional[User] = strawberry_django.field(select_related=["creator__profile"])
    date_published: strawberry.auto
    header_image: Optional[str]
    header_image_blurhash: Optional[str]
    topic: Optional[Topic]

    @strawberry_django.field()
    def posts(self, info) -> List[Annotated["Post", strawberry.lazy("openbook_posts.schema.types")]]:
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

    @strawberry_django.field(
        description="A list of all users involved. Curator of the insight, Authors of all the posts and all commenters of those posts"
    )
    def involved_users(self, info, offset: int = 0, limit: int = 3) -> Paged[User]:
        current_user = info.context.request.user
        query = UserModel.objects.filter(
            Q(
                Q(curated_insights=self)
                | (Q(posts__insights=self) & PostModel.is_visible_query(current_user, "posts"))
                | (
                    Q(posts_comments__post__insights=self)
                    & PostCommentModel.is_visible_query(current_user, "posts_comments")
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
    def is_bookmarked(self, info) -> bool:
        current_user = info.context.request.user
        if current_user.is_anonymous:
            return False

        return current_user.profile.favorite_insights.filter(id=self.id).exists()

    @strawberry_django.field()
    def quote(self, id: uuid.UUID) -> Quote:
        return self.quotes.get(id=id)
    
    @strawberry_django.field()
    def recommendation(self, id: uuid.UUID) -> Recommendation:
        return self.recommendations.get(id=id)

