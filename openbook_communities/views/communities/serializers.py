from django.conf import settings
from rest_framework import serializers

from openbook.settings import COLOR_ATTR_MAX_LENGTH
from openbook_categories.models import Category
from openbook_categories.validators import category_name_exists
from openbook_common.serializers import CommonCommunityMembershipSerializer
from openbook_common.serializers_fields.community import CommunityPostsCountField
from openbook_common.serializers_fields.request import RestrictedImageFileSizeField
from openbook_common.validators import hex_color_validator
from openbook_communities.models import Community
from openbook_communities.serializers_fields import (
    IsInvitedField,
    IsCreatorField,
    CommunityMembershipsField,
    IsFavoriteField,
    AreNewPostNotificationsEnabledForCommunityField,
)
from openbook_communities.validators import (
    community_name_characters_validator,
    community_name_not_taken_validator,
    community_id_exists,
    sdg_with_id_exists,
    topic_with_id_exists,
)


class CreateCommunitySerializer(serializers.Serializer):
    type = serializers.ChoiceField(allow_blank=False, required=False, choices=Community.COMMUNITY_TYPES)
    title = serializers.CharField(
        min_length=settings.COMMUNITY_TITLE_MIN_LENGTH,
        max_length=settings.COMMUNITY_TITLE_MAX_LENGTH,
        required=True,
    )
    description = serializers.CharField(
        max_length=settings.COMMUNITY_DESCRIPTION_MAX_LENGTH,
        required=True,
    )
    rules = serializers.CharField(max_length=settings.COMMUNITY_RULES_MAX_LENGTH, allow_blank=True, required=False)
    user_adjective = serializers.CharField(
        max_length=settings.COMMUNITY_USER_ADJECTIVE_MAX_LENGTH,
        allow_blank=False,
        required=False,
    )
    users_adjective = serializers.CharField(
        max_length=settings.COMMUNITY_USERS_ADJECTIVE_MAX_LENGTH,
        allow_blank=False,
        required=False,
    )
    avatar = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.COMMUNITY_AVATAR_MAX_SIZE,
    )
    cover = RestrictedImageFileSizeField(
        required=True,
        max_upload_size=settings.COMMUNITY_COVER_MAX_SIZE,
        allow_empty_file=False,
    )
    invites_enabled = serializers.BooleanField(required=False)
    color = serializers.CharField(
        max_length=COLOR_ATTR_MAX_LENGTH,
        required=False,
        validators=[hex_color_validator],
    )
    categories = serializers.ListField(
        required=False,
        min_length=settings.COMMUNITY_CATEGORIES_MIN_AMOUNT,
        max_length=settings.COMMUNITY_CATEGORIES_MAX_AMOUNT,
        child=serializers.CharField(
            max_length=settings.HASHTAG_NAME_MAX_LENGTH,
            validators=[category_name_exists],
        ),
    )
    topics = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=True,
        child=serializers.UUIDField(validators=[topic_with_id_exists]),
    )


class ValidateCommunitySerializer(serializers.Serializer):
    title = serializers.CharField(
        min_length=settings.COMMUNITY_TITLE_MIN_LENGTH,
        max_length=settings.COMMUNITY_TITLE_MAX_LENGTH,
        required=True,
    )
    description = serializers.CharField(
        max_length=settings.COMMUNITY_DESCRIPTION_MAX_LENGTH,
        required=True,
    )
    topics = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[topic_with_id_exists]),
    )
    cover = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.COMMUNITY_COVER_MAX_SIZE,
    )
    sdgs = serializers.ListField(
        required=False,
        child=serializers.UUIDField(validators=[sdg_with_id_exists]),
    )
    location = serializers.CharField(
        max_length=settings.COMMUNITY_LOCATION_MAX_LENGTH,
        required=False,
    )


class UpdateCommunitySerializer(serializers.Serializer):
    id = serializers.UUIDField(
        validators=[community_id_exists],
        required=True,
    )
    title = serializers.CharField(
        min_length=settings.COMMUNITY_TITLE_MIN_LENGTH,
        max_length=settings.COMMUNITY_TITLE_MAX_LENGTH,
        required=False,
    )
    description = serializers.CharField(
        max_length=settings.COMMUNITY_DESCRIPTION_MAX_LENGTH,
        required=False,
    )
    topics = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[topic_with_id_exists]),
    )
    cover = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.COMMUNITY_COVER_MAX_SIZE,
    )
    avatar = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.COMMUNITY_AVATAR_MAX_SIZE,
    )
    sdgs = serializers.ListField(
        required=False,
        child=serializers.UUIDField(validators=[sdg_with_id_exists]),
    )
    location = serializers.CharField(
        max_length=settings.COMMUNITY_LOCATION_MAX_LENGTH,
        required=False,
    )


class CommunityNameCheckSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=settings.COMMUNITY_NAME_MAX_LENGTH,
        allow_blank=False,
        validators=[
            community_name_characters_validator,
            community_name_not_taken_validator,
        ],
    )


class GetJoinedCommunitiesSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    offset = serializers.IntegerField(
        required=False,
    )


class GetModeratedCommunitiesSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    offset = serializers.IntegerField(
        required=False,
    )


class GetAdministratedCommunitiesSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    offset = serializers.IntegerField(
        required=False,
    )


class GetFavoriteCommunitiesSerializer(serializers.Serializer):
    count = serializers.IntegerField(required=False, max_value=20)
    offset = serializers.IntegerField(
        required=False,
    )


class TrendingCommunitiesSerializer(serializers.Serializer):
    category = serializers.CharField(
        max_length=settings.CATEGORY_NAME_MAX_LENGTH,
        allow_blank=True,
        required=False,
        validators=[category_name_exists],
    )


class GetCommunitiesCommunityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "title", "color")


class CommunitiesCommunitySerializer(serializers.ModelSerializer):
    categories = GetCommunitiesCommunityCategorySerializer(many=True)
    is_invited = IsInvitedField()
    are_new_post_notifications_enabled = AreNewPostNotificationsEnabledForCommunityField()
    is_favorite = IsFavoriteField()
    is_creator = IsCreatorField()
    posts_count = CommunityPostsCountField()
    memberships = CommunityMembershipsField(community_membership_serializer=CommonCommunityMembershipSerializer)

    class Meta:
        model = Community
        fields = (
            "id",
            "name",
            "title",
            "avatar",
            "cover",
            "members_count",
            "posts_count",
            "avatar_default_color",
            "color",
            "user_adjective",
            "users_adjective",
            "categories",
            "type",
            "is_invited",
            "are_new_post_notifications_enabled",
            "is_favorite",
            "is_creator",
            "invites_enabled",
            "memberships",
        )


class SuggestedCommunitiesCommunitySerializer(serializers.ModelSerializer):
    is_creator = IsCreatorField()
    memberships = CommunityMembershipsField(community_membership_serializer=CommonCommunityMembershipSerializer)

    class Meta:
        model = Community
        fields = (
            "id",
            "name",
            "title",
            "avatar",
            "cover",
            "members_count",
            "color",
            "user_adjective",
            "users_adjective",
            "is_creator",
            "memberships",
        )
