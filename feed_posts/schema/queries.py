import uuid
import strawberry
import strawberry_django

from feed_posts.enums import VisibilityLevel
from feed_posts.schema.types import FeedPost, GenericPost
from feed_posts.services import FeedPostService
from openbook_common.schema.types import Paged
from openbook_posts.models import Post as PostModel


@strawberry.type
class Query:
    @strawberry_django.field()
    def my_posts(
        self,
        info,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[FeedPost]:
        user = info.context.request.user

        if user.is_anonymous:
            return Paged.empty()

        return Paged.of(
            FeedPostService().get_feed_posts_by_user_id(user_id=user.username),
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

    @strawberry_django.field()
    def post(
        self,
        info,
        id_or_slug: str,
    ) -> FeedPost:
        return FeedPostService().get_feed_post(user=info.context.request.user, id_or_slug=id_or_slug)

    @strawberry_django.field(deprecation_reason="feed_posts is deprecated, use all_posts instead.")
    def feed_posts(
        self,
        info,
        offset: int = 0,
        limit: int = 2,
    ) -> Paged[FeedPost]:
        user = info.context.request.user
        posts = FeedPostService().get_feed_posts()

        return Paged.of(
            posts.filter(visibility=VisibilityLevel.PUBLIC) if user.is_anonymous else posts,
            offset,
            limit,
        )

    @strawberry_django.field()
    def all_posts(
        self,
        info,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[GenericPost]:
        user = info.context.request.user

        feed_posts = FeedPostService().get_feed_posts()
        filtered_feed_posts = feed_posts.filter(visibility=VisibilityLevel.PUBLIC) if user.is_anonymous else feed_posts

        space_posts = PostModel.objects.filter(
            PostModel.is_visible_query(user), status=PostModel.STATUS_PUBLISHED, community__id__isnull=False
        ).distinct()

        posts = list(filtered_feed_posts) + list(space_posts)

        def get_creation_date(post):
            if hasattr(post, "created_at"):
                return post.created_at
            else:
                return post.created

        sorted_posts = sorted(
            posts,
            key=lambda post: (
                -int(getattr(post, "has_priority", False)),
                -get_creation_date(post).timestamp(),
            ),
        )

        start_index = offset
        end_index = offset + limit

        if start_index < 0:
            start_index = 0
        if end_index > len(sorted_posts):
            end_index = len(sorted_posts)

        return Paged(data=sorted_posts[start_index:end_index], total_results=len(sorted_posts))
