from django.conf import settings
from rest_framework import serializers

from comments.models import Comment, CommentReaction
from openbook_common.models import Emoji
from openbook_common.serializers import CommonHashtagSerializer
from openbook_common.serializers_fields.post_comment import (
    PostCommenterField,
    PostCommentIsMutedField,
    PostCommentReactionField,
    PostCommentReactionsEmojiCountField,
)
from openbook_posts.serializers.post_comments_serializers import (
    PostCommentCommenterSerializer,
    PostCommenterCommunityMembershipSerializer,
    PostCommentLanguageSerializer,
)
from openbook_posts.validators import (
    post_comment_id_exists,
    post_comment_text_validators,
    post_id_exists,
)


class CommentRepliesPostSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    post_comment_id = serializers.UUIDField(
        validators=[post_comment_id_exists],
        required=True,
    )
    text = serializers.CharField(
        max_length=settings.POST_COMMENT_MAX_LENGTH,
        required=True,
        allow_blank=False,
        validators=post_comment_text_validators,
    )


class PostCommentReplyParentSerializer(serializers.ModelSerializer):
    language = PostCommentLanguageSerializer()

    class Meta:
        model = Comment
        fields = ("id", "language")


class PostCommentReactionEmojiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emoji
        fields = (
            "id",
            "keyword",
            "image",
            "created",
        )


class PostEmojiCountSerializer(serializers.Serializer):
    emoji = PostCommentReactionEmojiSerializer(many=False)
    count = serializers.IntegerField(
        required=True,
    )


class PostCommentReactionSerializer(serializers.ModelSerializer):
    emoji = PostCommentReactionEmojiSerializer(many=False)

    class Meta:
        model = CommentReaction
        fields = ("emoji", "id")


class PostCommentReplySerializer(serializers.ModelSerializer):
    commenter = PostCommenterField(
        post_commenter_serializer=PostCommentCommenterSerializer,
        community_membership_serializer=PostCommenterCommunityMembershipSerializer,
    )
    parent_comment = PostCommentReplyParentSerializer()
    reactions_emoji_counts = PostCommentReactionsEmojiCountField(emoji_count_serializer=PostEmojiCountSerializer)
    reaction = PostCommentReactionField(post_comment_reaction_serializer=PostCommentReactionSerializer)
    is_muted = PostCommentIsMutedField()
    language = PostCommentLanguageSerializer()
    hashtags = CommonHashtagSerializer(many=True)

    class Meta:
        model = Comment
        fields = (
            "commenter",
            "reactions_emoji_counts",
            "reaction",
            "text",
            "language",
            "created",
            "parent_comment",
            "is_edited",
            "is_muted",
            "hashtags",
            "id",
        )


class GetPostCommentRepliesSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    post_comment_id = serializers.UUIDField(
        validators=[post_comment_id_exists],
        required=True,
    )
    max_id = serializers.IntegerField(
        required=False,
    )
    min_id = serializers.IntegerField(
        required=False,
    )
    count_max = serializers.IntegerField(required=False, max_value=20)
    count_min = serializers.IntegerField(required=False, max_value=20)
    sort = serializers.ChoiceField(required=False, choices=["ASC", "DESC"])
