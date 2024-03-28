from django.conf import settings
from rest_framework import serializers

from comments.models import Comment, CommentReaction
from comments.validators import comment_text_validators
from openbook_auth.models import User, UserProfile
from openbook_common.models import Emoji, Language
from openbook_common.serializers import (
    CommonHashtagSerializer,
    CommonUserProfileBadgeSerializer,
)
from openbook_common.serializers_fields.post_comment import (
    PostCommenterField,
    PostCommentIsMutedField,
    PostCommentReactionField,
    PostCommentReactionsEmojiCountField,
    RepliesCountField,
)
from openbook_communities.models import CommunityMembership
from openbook_posts.models import Post
from openbook_posts.serializers.post_comments_serializer_fields import RepliesField
from openbook_posts.validators import post_id_exists


class PostCommenterProfileSerializer(serializers.ModelSerializer):
    badges = CommonUserProfileBadgeSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ("avatar", "badges", "name")


class PostCommentCommenterSerializer(serializers.ModelSerializer):
    profile = PostCommenterProfileSerializer(many=False)

    class Meta:
        model = User
        fields = ("username", "profile", "id")


class PostCommenterCommunityMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityMembership
        fields = (
            "id",
            "user_id",
            "community_id",
            "is_administrator",
            "is_moderator",
        )


class PostCommentLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = (
            "id",
            "code",
            "name",
        )


class PostCommentRepliesParentCommentSerializer(serializers.ModelSerializer):
    language = PostCommentLanguageSerializer()

    class Meta:
        model = Comment
        fields = (
            "id",
            "language",
        )


class PostCommentReactionEmojiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Emoji
        fields = (
            "id",
            "keyword",
            "image",
            "created",
        )


class PostCommentReactionEmojiCountSerializer(serializers.Serializer):
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
    parent_comment = PostCommentRepliesParentCommentSerializer()
    commenter = PostCommenterField(
        post_commenter_serializer=PostCommentCommenterSerializer,
        community_membership_serializer=PostCommenterCommunityMembershipSerializer,
    )
    reactions_emoji_counts = PostCommentReactionsEmojiCountField(
        emoji_count_serializer=PostCommentReactionEmojiCountSerializer
    )
    reaction = PostCommentReactionField(post_comment_reaction_serializer=PostCommentReactionSerializer)
    is_muted = PostCommentIsMutedField()
    language = PostCommentLanguageSerializer()
    hashtags = CommonHashtagSerializer(many=True)

    class Meta:
        model = Comment
        fields = (
            "commenter",
            "parent_comment",
            "text",
            "language",
            "created",
            "is_edited",
            "is_muted",
            "reactions_emoji_counts",
            "id",
            "reaction",
            "hashtags",
        )


class PostCommentSerializer(serializers.ModelSerializer):
    commenter = PostCommenterField(
        post_commenter_serializer=PostCommentCommenterSerializer,
        community_membership_serializer=PostCommenterCommunityMembershipSerializer,
    )
    replies = RepliesField(post_comment_reply_serializer=PostCommentReplySerializer)
    replies_count = RepliesCountField()
    reactions_emoji_counts = PostCommentReactionsEmojiCountField(
        emoji_count_serializer=PostCommentReactionEmojiCountSerializer
    )
    reaction = PostCommentReactionField(post_comment_reaction_serializer=PostCommentReactionSerializer)
    is_muted = PostCommentIsMutedField()
    language = PostCommentLanguageSerializer()
    hashtags = CommonHashtagSerializer(many=True)

    class Meta:
        model = Comment
        fields = (
            "commenter",
            "text",
            "language",
            "created",
            "reactions_emoji_counts",
            "replies_count",
            "replies",
            "reaction",
            "is_edited",
            "is_muted",
            "hashtags",
            "id",
        )


class CommentPostSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
    text = serializers.CharField(
        max_length=settings.POST_COMMENT_MAX_LENGTH,
        required=True,
        allow_blank=False,
        validators=comment_text_validators,
    )


class GetPostCommentsSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
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


class EnableDisableCommentsPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ("id", "comments_enabled")


class DisableCommentsPostSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )


class EnableCommentsPostSerializer(serializers.Serializer):
    post_id = serializers.UUIDField(
        validators=[post_id_exists],
        required=True,
    )
