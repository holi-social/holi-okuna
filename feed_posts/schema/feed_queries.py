from collections import OrderedDict
from datetime import timedelta
from asgiref.sync import sync_to_async

import strawberry
import strawberry_django
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, OuterRef, Subquery, Prefetch
from django.db.models.functions import Coalesce
from django.utils import timezone

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


@strawberry.type
class Query:
    # This is the first iteration of home feed personalization.
    # The query is not intended to be performant or optimized at this stage, but rather to ensure all personalization requirements are met.
    # Effort on optimization or performance improvements should only be made if this iteration performs worse than the current all_posts query.
    @strawberry_django.field()
    @sync_to_async
    def feed(
        self,
        info,
        offset: int = 0,
        limit: int = 10,
    ) -> Paged[FeedItem]:
        user = info.context.request.user

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

        base_space_posts = (
            PostModel.objects.filter(
                PostModel.is_visible_query(user), status=PostModel.STATUS_PUBLISHED, community__id__isnull=False
            )
            .select_related("creator", "community")
            .prefetch_related("reactions", "community__topics")
            .annotate(
                reaction_count=Count("reactions"),
                total_comments=Subquery(space_comments_subquery, output_field=models.IntegerField()),
            )
            .defer("mentions")
            .order_by("-created", "-reaction_count", "-total_comments")
            .distinct()
        )

        if user.is_anonymous:
            feed_posts = (
                FeedPostModel.objects.filter(visibility=VisibilityLevel.PUBLIC)
                .select_related("creator")
                .prefetch_related("reactions", "topics")
                .annotate(
                    reaction_count=Count("reactions"),
                    total_comments=Subquery(feed_post_comments_subquery, output_field=models.IntegerField()),
                )
                .order_by("-created_at", "-reaction_count", "-total_comments")
            )

            sorted_posts = sorted(
                feed_posts,
                key=lambda post: (-int(getattr(post, "has_priority", False)),),
            )

            posts = list(sorted_posts) + list(base_space_posts)
            feed_items = [map_to_feed_item(post) for post in posts]
            return paginate_posts(feed_items, offset, limit)

        # Authenticated users
        feed_config = FeedConfig.objects.select_related().first()
        priority_duration = timedelta(days=feed_config.priority_duration) if feed_config else timedelta(days=7)

        base_feed_posts = (
            FeedPostModel.objects.select_related("creator")
            .prefetch_related("reactions", "topics")
            .annotate(
                reaction_count=Count("reactions"),
                total_comments=Coalesce(Subquery(feed_post_comments_subquery, output_field=models.IntegerField()), 0),
            )
            .order_by("-created_at", "-reaction_count", "-total_comments")
        )

        user_interests = list(user.profile.interests.values_list("id", flat=True))
        user_connections = list(user.connections.values_list("target_user_id", flat=True))
        current_time = timezone.now()

        post_lists = []

        # User recently created posts
        post_lists.append(
            list(base_feed_posts.filter(creator=user, created_at__gte=current_time - timedelta(hours=1)))
        )

        # User recently created space posts
        post_lists.append(
            list(
                base_space_posts.filter(
                    creator=user,
                    created__gte=current_time - timedelta(hours=1),
                )
            )
        )

        # Co-founders and priority posts
        priority_posts = [
            post
            for post in base_feed_posts
            if post.has_priority or post.created_at >= current_time - timedelta(days=post.priority_duration)
        ]
        post_lists.append(priority_posts)

        # User connections posts
        post_lists.append(
            list(
                base_feed_posts.filter(
                    creator__id__in=user_connections, created_at__gte=current_time - priority_duration
                )
            )
        )

        # Space posts - user collaborator/follower
        space_posts_user = base_space_posts.filter(
            models.Q(community__memberships__user=user)
            | models.Q(
                community__notifications_subscriptions__subscriber=user,
                community__notifications_subscriptions__new_post_notifications=True,
            ),
            created__gte=current_time - priority_duration,
        )
        post_lists.append(list(space_posts_user))

        # Posts matching user's topics
        topic_posts = base_feed_posts.filter(
            topics__id__in=user_interests, created_at__gte=current_time - priority_duration
        )
        post_lists.append(list(topic_posts))

        space_topic_posts = base_space_posts.filter(
            community__topics__id__in=user_interests, created__gte=current_time - priority_duration
        )
        post_lists.append(list(space_topic_posts))

        # Editors posts
        editor_posts = base_feed_posts.filter(
            creator__role=UserRole.EDITOR, created_at__gte=current_time - priority_duration
        )
        post_lists.append(list(editor_posts))

        # Latest posts
        latest_feed = base_feed_posts.filter(creator=user, created_at__gte=current_time - timedelta(days=1))
        post_lists.append(list(latest_feed))

        latest_space = base_space_posts.filter(
            creator=user,
            created__gte=current_time - timedelta(days=1),
        )
        post_lists.append(list(latest_space))

        # All remaining posts
        post_lists.append(list(base_feed_posts))
        post_lists.append(list(base_space_posts))

        # Use OrderedDict to maintain order and remove duplicates
        all_posts = OrderedDict()
        for post_list in post_lists:
            for post in post_list:
                all_posts[post] = None

        posts = list(all_posts.keys())
        feed_items = [map_to_feed_item(post) for post in posts]

        return paginate_posts(feed_items, offset, limit)
