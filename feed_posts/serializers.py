from rest_framework import serializers

from feed_posts.enums import VisibilityLevel
from feed_posts.validators import validate_topic_exists_by_id, validate_feed_post_category_exists_by_id
from openbook import settings


class CreateFeedPostSerializer(serializers.Serializer):
    title = serializers.CharField(
        min_length=settings.FEED_POST_TITLE_MIN_LENGTH,
        max_length=settings.FEED_POST_TITLE_MAX_LENGTH,
        required=True,
    )

    description = serializers.CharField(
        min_length=settings.FEED_POST_DESCRIPTION_MIN_LENGTH,
        max_length=settings.FEED_POST_DESCRIPTION_MAX_LENGTH,
        required=True,
    )

    visibility = serializers.ChoiceField(required=True, choices=VisibilityLevel.choices)

    topic_ids = serializers.ListField(
        max_length=settings.FEED_POST_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[validate_topic_exists_by_id]),
    )

    category_id = serializers.UUIDField(required=True, validators=[validate_feed_post_category_exists_by_id])
