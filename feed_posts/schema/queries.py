import uuid

import strawberry
import strawberry_django

from feed_posts.enums import VisibilityLevel
from feed_posts.schema.types import FeedPost
from feed_posts.services import FeedPostService
from openbook_auth.utils import verify_authorized_user
from openbook_common.schema.types import Paged


@strawberry.type
class Query:
    @strawberry_django.field()
    def my_posts(
        self,
        info,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[FeedPost]:
        user = verify_authorized_user(info)

        return Paged.of(
            FeedPostService().get_feed_posts_by_user_id(user_id=user.pk),
            offset,
            limit,
        )

    @strawberry_django.field()
    def posts_by_user_id(
        self,
        info,
        user_id: uuid.UUID,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[FeedPost]:
        current_user = info.context.request.user
        posts = FeedPostService().get_feed_posts_by_user_id(user_id)

        return Paged.of(
            posts.filter(visibility=VisibilityLevel.PUBLIC) if current_user.is_anonymous else posts,
            offset,
            limit,
        )
