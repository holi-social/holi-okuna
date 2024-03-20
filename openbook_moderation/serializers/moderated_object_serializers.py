from django.conf import settings
from generic_relations.relations import GenericRelatedField
from rest_framework import serializers

from openbook_auth.models import User, UserProfile
from openbook_common.models import Badge, Language
from openbook_common.serializers import (
    CommonEmojiSerializer,
    CommonPublicUserSerializer,
)
from openbook_common.serializers_fields.hashtag import HashtagPostsCountField
from openbook_common.serializers_fields.post import IsEncircledField
from openbook_communities.models import Community
from openbook_hashtags.models import Hashtag
from openbook_moderation.models import (
    ModeratedObject,
    ModeratedObjectCategoryChangedLog,
    ModeratedObjectDescriptionChangedLog,
    ModeratedObjectLog,
    ModeratedObjectStatusChangedLog,
    ModeratedObjectVerifiedChangedLog,
    ModerationCategory,
    ModerationReport,
)
from openbook_moderation.serializers.validators import (
    moderated_object_id_exists,
    moderation_category_id_exists,
)
from openbook_posts.models import Post, PostComment, PostImage


class ModeratedObjectUserProfileBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("keyword", "keyword_description")


class UpdateModeratedObjectSerializer(serializers.Serializer):
    description = serializers.CharField(
        max_length=settings.MODERATED_OBJECT_DESCRIPTION_MAX_LENGTH,
        required=False,
        allow_blank=False,
    )
    moderated_object_id = serializers.UUIDField(
        validators=[moderated_object_id_exists],
        required=True,
    )
    category_id = serializers.UUIDField(validators=[moderation_category_id_exists], required=False)


class ApproveModeratedObjectSerializer(serializers.Serializer):
    moderated_object_id = serializers.UUIDField(
        validators=[moderated_object_id_exists],
        required=True,
    )


class RejectModeratedObjectSerializer(serializers.Serializer):
    moderated_object_id = serializers.UUIDField(
        validators=[moderated_object_id_exists],
        required=True,
    )


class VerifyModeratedObjectSerializer(serializers.Serializer):
    moderated_object_id = serializers.UUIDField(
        validators=[moderated_object_id_exists],
        required=True,
    )


class UnverifyModeratedObjectSerializer(serializers.Serializer):
    moderated_object_id = serializers.UUIDField(
        validators=[moderated_object_id_exists],
        required=True,
    )


class GetModeratedObjectLogsSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    max_id = serializers.IntegerField(
        required=False,
    )
    moderated_object_id = serializers.UUIDField(
        validators=[moderated_object_id_exists],
        required=True,
    )


class ModeratedObjectLogModerationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ModerationCategory
        fields = (
            "id",
            "name",
            "title",
            "description",
            "severity",
        )


class ModeratedObjectLogActorProfileSerializer(serializers.ModelSerializer):
    badges = ModeratedObjectUserProfileBadgeSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ("id", "avatar", "badges")


class ModeratedObjectLogActorSerializer(serializers.ModelSerializer):
    profile = ModeratedObjectLogActorProfileSerializer()

    class Meta:
        model = User
        fields = ("id", "username", "profile")


class ModeratedObjectCategoryChangedLogSerializer(serializers.ModelSerializer):
    changed_from = ModeratedObjectLogModerationCategorySerializer()
    changed_to = ModeratedObjectLogModerationCategorySerializer()

    class Meta:
        model = ModeratedObjectCategoryChangedLog
        fields = ("id", "changed_from", "changed_to")


class ModeratedObjectDescriptionChangedLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeratedObjectDescriptionChangedLog
        fields = ("id", "changed_from", "changed_to")


class ModeratedObjectStatusChangedLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeratedObjectStatusChangedLog
        fields = ("id", "changed_from", "changed_to")


class ModeratedObjectVerifiedChangedLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeratedObjectVerifiedChangedLog
        fields = ("id", "changed_from", "changed_to")


class ModeratedObjectLogSerializer(serializers.ModelSerializer):
    actor = ModeratedObjectLogActorSerializer()

    content_object = GenericRelatedField(
        {
            ModeratedObjectCategoryChangedLog: ModeratedObjectCategoryChangedLogSerializer(),
            ModeratedObjectDescriptionChangedLog: ModeratedObjectDescriptionChangedLogSerializer(),
            ModeratedObjectStatusChangedLog: ModeratedObjectStatusChangedLogSerializer(),
            ModeratedObjectVerifiedChangedLog: ModeratedObjectVerifiedChangedLogSerializer(),
        }
    )

    class Meta:
        model = ModeratedObjectLog
        fields = ("id", "log_type", "actor", "content_object", "created")


class ModeratedObjectReportReporterProfileSerializer(serializers.ModelSerializer):
    badges = ModeratedObjectUserProfileBadgeSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = ("id", "avatar", "name", "badges")


class ModeratedObjectReportReporterSerializer(serializers.ModelSerializer):
    profile = ModeratedObjectReportReporterProfileSerializer()

    class Meta:
        model = User
        fields = ("id", "username", "profile")


class GetModeratedObjectReportsSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    max_id = serializers.IntegerField(
        required=False,
    )
    moderated_object_id = serializers.UUIDField(
        validators=[moderated_object_id_exists],
        required=True,
    )


class ModeratedObjectReportModerationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ModerationCategory
        fields = (
            "id",
            "name",
            "title",
            "description",
            "severity",
        )


class ModeratedObjectReportSerializer(serializers.ModelSerializer):
    category = ModeratedObjectReportModerationCategorySerializer()
    reporter = ModeratedObjectReportReporterSerializer()

    class Meta:
        model = ModerationReport
        fields = (
            "id",
            "category",
            "description",
            "reporter",
        )


class ModeratedObjectHashtagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hashtag
        fields = ("id", "name", "posts_count")


class ModeratedObjectCommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ("id", "name", "title", "avatar", "description", "color")


class ModeratedObjectHashtagSerializer(serializers.ModelSerializer):
    emoji = CommonEmojiSerializer()
    posts_count = HashtagPostsCountField(show_all=True)

    class Meta:
        model = Hashtag
        fields = ("id", "name", "color", "text_color", "image", "emoji", "posts_count")


class ModeratedObjectPostImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostImage
        fields = ("id", "image", "width", "height")


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = (
            "id",
            "code",
            "name",
        )


class ModeratedObjectPostSerializer(serializers.ModelSerializer):
    creator = CommonPublicUserSerializer()
    community = ModeratedObjectCommunitySerializer()
    image = ModeratedObjectPostImageSerializer()
    language = LanguageSerializer()
    is_encircled = IsEncircledField()

    class Meta:
        model = Post
        fields = (
            "id",
            "text",
            "language",
            "creator",
            "community",
            "image",
            "created",
            "comments_enabled",
            "is_closed",
            "is_encircled",
        )


class ModeratedObjectPostCommentSerializer(serializers.ModelSerializer):
    commenter = CommonPublicUserSerializer()
    post = ModeratedObjectPostSerializer()
    language = LanguageSerializer()

    class Meta:
        model = PostComment
        fields = (
            "id",
            "text",
            "language",
            "commenter",
            "commenter",
            "created",
            "commentable_id",
            "commentable",
            "is_edited",
        )


class ModerationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ModerationCategory
        fields = (
            "id",
            "name",
            "title",
            "description",
        )


class ModeratedObjectSerializer(serializers.ModelSerializer):
    category = ModerationCategorySerializer()

    content_object = GenericRelatedField(
        {
            Post: ModeratedObjectPostSerializer(),
            PostComment: ModeratedObjectPostCommentSerializer(),
            Community: ModeratedObjectCommunitySerializer(),
            User: CommonPublicUserSerializer(),
            Hashtag: ModeratedObjectHashtagSerializer(),
        }
    )

    class Meta:
        model = ModeratedObject
        fields = (
            "id",
            "object_type",
            "object_id",
            "content_object",
            "verified",
            "status",
            "description",
            "category",
            "reports_count",
        )
