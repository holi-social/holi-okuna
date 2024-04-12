from rest_framework.exceptions import NotFound
from django.utils.translation import gettext_lazy as _

from openbook_terms.models import Topic, FeedPostCategory


def validate_topic_exists_by_id(topic_uuid):
    if not Topic.objects.filter(id=topic_uuid).exists():
        raise NotFound(_(f"No topic with the id '{topic_uuid}' found."))


def validate_feed_post_category_exists_by_id(topic_uuid):
    if not FeedPostCategory.objects.filter(id=topic_uuid).exists():
        raise NotFound(_(f"No feed post category with the id '{topic_uuid}' found."))
