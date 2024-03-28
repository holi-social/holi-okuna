from django.conf import settings
from rest_framework import serializers

from openbook_posts.validators import post_comment_text_validators, post_id_exists


class CommentSerializer(serializers.Serializer):
    commentable_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    text = serializers.CharField(
        max_length=settings.POST_COMMENT_MAX_LENGTH,
        required=True,
        allow_blank=False,
        validators=post_comment_text_validators,
    )
