from collections import OrderedDict
from datetime import timedelta

import strawberry
import strawberry_django
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.cache import cache

from comments.models import Comment
from feed_posts.enums import VisibilityLevel
from feed_posts.schema.types import FeedItem
from feed_posts.models import FeedPost as FeedPostModel, FeedConfig
from openbook_auth.models import UserRole
from openbook_common.schema.types import Paged
from openbook_insights.models import Insight as InsightModel
from openbook_posts.models import Post as PostModel


def paginate_posts(posts, offset, limit):
    start_index = max(0, offset)
    end_index = min(offset + limit, len(posts))
    return Paged(data=posts[start_index:end_index], total_results=len(posts))


def map_to_feed_item(post):
    if isinstance(post, FeedPostModel):
        return FeedItem(feed_post=post, insight=None, space_post=None)
    elif isinstance(post, InsightModel):
        return FeedItem(feed_post=None, insight=post, space_post=None)
    elif isinstance(post, PostModel):
        return FeedItem(feed_post=None, insight=None, space_post=post)
    else:
        return None


def get_creation_date(post):
    if hasattr(post, "created_at"):
        return post.created_at
    else:
        return post.created


@strawberry.type
class Query:
    # This is the first iteration of home feed personalization.
    # The query is not intended to be performant or optimized at this stage, but rather to ensure all personalization requirements are met.
    # Effort on optimization or performance improvements should only be made if this iteration performs worse than the current all_posts query.
    @strawberry_django.field()
    def feed(
        self,
        info,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[FeedItem]:
        user = info.context.request.user

        # Generate cache key based on user and pagination
        cache_key = f"feed:{user.id if user.is_authenticated else 'anon'}:o{offset}:l{limit}"
        cached_feed = cache.get(cache_key)
        if cached_feed:
            return cached_feed

        feed_post_content_type = ContentType.objects.get_for_model(FeedPostModel)
        space_post_content_type = ContentType.objects.get_for_model(PostModel)

        # Count feed post comments
        feed_post_comments_subquery = (
            Comment.objects.filter(
                commentable_id=OuterRef("pk"),
                commentable_type=feed_post_content_type,
                is_deleted=False,
            )
            .values("commentable_id")
            .annotate(total=Count("id"))
            .values("total")
        )

        # Count space post comments
        space_comments_subquery = (
            Comment.objects.filter(
                commentable_id=OuterRef("pk"),
                commentable_type=space_post_content_type,
                is_deleted=False,
            )
            .values("commentable_id")
            .annotate(total=Count("id"))
            .values("total")
        )

        space_posts = (
            PostModel.objects.filter(
                PostModel.is_visible_query(user), status=PostModel.STATUS_PUBLISHED, community__id__isnull=False
            )
            .annotate(
                reaction_count=Count("reactions"),
                total_comments=Subquery(space_comments_subquery, output_field=models.IntegerField()),
            )
            .select_related("community")
            .defer("mentions")
            .order_by("-created", "-reaction_count", "-total_comments")
            .distinct()
        )

        if user.is_anonymous:
            feed_posts = (
                FeedPostModel.objects.filter(visibility=VisibilityLevel.PUBLIC)
                .annotate(
                    reaction_count=Count("reactions"),
                    total_comments=Subquery(feed_post_comments_subquery, output_field=models.IntegerField()),
                )
                .select_related("creator")
                .order_by("-created_at", "-reaction_count", "-total_comments")
            )

            posts = list(feed_posts) + list(space_posts)

            sorted_posts = sorted(
                posts,
                key=lambda post: (
                    -int(getattr(post, "has_priority", False)),
                    -get_creation_date(post).timestamp(),
                ),
            )

            feed_items = [map_to_feed_item(post) for post in sorted_posts]
            result = paginate_posts(feed_items, offset, limit)

            # Cache anonymous results for 10 minutes
            cache.set(cache_key, result, 600)
            return result

        # Authenticated users

        feed_config = FeedConfig.objects.first()
        priority_duration = timedelta(days=feed_config.priority_duration) if feed_config else timedelta(days=7)

        feed_posts = (
            FeedPostModel.objects.annotate(
                reaction_count=Count("reactions"),
                total_comments=Coalesce(Subquery(feed_post_comments_subquery, output_field=models.IntegerField()), 0),
            )
            .select_related("creator")
            .order_by("-created_at", "-reaction_count", "-total_comments")
        )

        user_interests_v2 = user.profile.interests_v2
        user_connections = user.connections.values_list("target_user_id", flat=True)
        current_time = timezone.now()

        unsorted_posts = list(feed_posts) + list(space_posts)

        sorted_posts = sorted(
            unsorted_posts,
            key=lambda post: (-get_creation_date(post).timestamp(),),
        )

        # Build post lists in order of priority
        post_lists = [
            # User recently created posts
            feed_posts.filter(creator=user, created_at__gte=current_time - timedelta(hours=1)),
            # User recently created space posts
            PostModel.objects.filter(
                creator=user,
                status=PostModel.STATUS_PUBLISHED,
                created__gte=current_time - timedelta(hours=1),
            )
            .defer("mentions")
            .order_by("-created")
            .distinct(),
            # Co-founders
            [post for post in feed_posts if post.has_priority],
            [post for post in feed_posts if post.created_at >= current_time - timedelta(days=post.priority_duration)],
            # User connections posts
            feed_posts.filter(creator__id__in=user_connections, created_at__gte=current_time - priority_duration),
            # Space posts in spaces that the user is collaborator
            space_posts.filter(community__memberships__user=user, created__gte=current_time - priority_duration),
            # Space posts user is follower of
            space_posts.filter(
                community__notifications_subscriptions__subscriber=user,
                community__notifications_subscriptions__new_post_notifications=True,
                created__gte=current_time - priority_duration,
            ),
            # Feed posts matching user's topics
            feed_posts.filter(topics_v2__overlap=user_interests_v2, created_at__gte=current_time - priority_duration),
            # Space posts matching user's topics
            space_posts.filter(
                community__topics_v2__overlap=user_interests_v2, created__gte=current_time - priority_duration
            ),
            # Editors posts
            feed_posts.filter(creator__role=UserRole.EDITOR, created_at__gte=current_time - priority_duration),
            # Latest feed posts
            feed_posts.filter(creator=user, created_at__gte=current_time - timedelta(days=1)),
            # Latest space posts
            PostModel.objects.filter(
                creator=user,
                status=PostModel.STATUS_PUBLISHED,
                created__gte=current_time - timedelta(days=1),
            )
            .defer("mentions")
            .order_by("-created")
            .distinct(),
            sorted_posts,
        ]

        # Combine all posts while preserving order and removing duplicates
        all_posts = OrderedDict()
        for post_list in post_lists:
            for post in post_list:
                all_posts[post] = None

        posts = list(all_posts.keys())
        feed_items = [map_to_feed_item(post) for post in posts]
        result = paginate_posts(feed_items, offset, limit)

        # Cache authenticated user results for 2 minutes
        cache.set(cache_key, result, 120)
        return result
