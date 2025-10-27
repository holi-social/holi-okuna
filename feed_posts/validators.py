from rest_framework.exceptions import NotFound
from django.utils.translation import gettext_lazy as _

from feed_posts.services import FeedPostService
from openbook_terms.models import FeedPostCategory


def validate_feed_post_category_exists_by_id(feed_post_uuid):
    if not FeedPostCategory.objects.filter(id=feed_post_uuid).exists():
        raise NotFound(_(f"No feed post category with the id '{feed_post_uuid}' found."))


def feed_post_exists(post_id):
    if not FeedPostService().exists(post_id=post_id):
        raise NotFound(_(f"Feed post with id {post_id} not found"))
