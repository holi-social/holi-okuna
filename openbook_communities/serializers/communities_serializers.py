from django.conf import settings
from rest_framework import serializers

from openbook.settings import COLOR_ATTR_MAX_LENGTH
from openbook_categories.models import Category
from openbook_categories.validators import category_name_exists
from openbook_common.serializers import CommonCommunityMembershipSerializer, GeolocationPointSerializer
from openbook_common.serializers_fields.community import CommunityPostsCountField
from openbook_common.serializers_fields.request import RestrictedImageFileSizeField
from openbook_common.validators import (
    hex_color_validator,
    url_safety_validator,
    sanitize_text,
    topic_v2_exists,
    skill_v2_exists,
)
from openbook_communities.models import CollaborationTool, Community, ExternalLinkType, Task, VisibilityType
from openbook_communities.serializers_fields import (
    IsInvitedField,
    IsCreatorField,
    CommunityMembershipsField,
    IsFavoriteField,
    AreNewPostNotificationsEnabledForCommunityField,
)
from openbook_communities.validators import (
    collaboration_tool_id_exists,
    community_name_characters_validator,
    community_name_not_taken_validator,
    community_id_exists,
    external_link_id_exists,
    task_id_exists,
    sdg_with_id_exists,
    topic_with_id_exists,
    skill_with_id_exists,
)


class CreateCommunitySerializer(serializers.Serializer):
    type = serializers.ChoiceField(allow_blank=False, required=False, choices=Community.COMMUNITY_TYPES)
    title = serializers.CharField(
        min_length=settings.COMMUNITY_TITLE_MIN_LENGTH,
        max_length=settings.COMMUNITY_TITLE_MAX_LENGTH,
        required=True,
    )
    description = serializers.CharField(
        max_length=settings.COMMUNITY_DESCRIPTION_MAX_LENGTH, required=True, validators=[sanitize_text]
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
        required=False,
        child=serializers.UUIDField(validators=[topic_with_id_exists]),
    )
    topics_v2 = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.CharField(validators=[topic_v2_exists]),
    )


class ValidateCommunitySerializer(serializers.Serializer):
    title = serializers.CharField(
        min_length=settings.COMMUNITY_TITLE_MIN_LENGTH,
        max_length=settings.COMMUNITY_TITLE_MAX_LENGTH,
        required=True,
    )
    description = serializers.CharField(
        max_length=settings.COMMUNITY_DESCRIPTION_MAX_LENGTH, required=True, validators=[sanitize_text]
    )
    topics = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[topic_with_id_exists]),
    )
    topics_v2 = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.CharField(validators=[topic_v2_exists]),
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


class UpdateOnboardingStepSerializer(serializers.Serializer):
    text = serializers.CharField(
        max_length=settings.ONBOARDING_STEP_TEXT_MAX_LENGTH,
        required=False,
        allow_blank=False,
        validators=[sanitize_text],
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
        max_length=settings.COMMUNITY_DESCRIPTION_MAX_LENGTH, required=False, validators=[sanitize_text]
    )
    topics = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[topic_with_id_exists]),
    )
    topics_v2 = serializers.ListField(
        min_length=settings.COMMUNITY_TOPICS_MIN_AMOUNT,
        max_length=settings.COMMUNITY_TOPICS_MAX_AMOUNT,
        required=False,
        child=serializers.CharField(max_length=settings.TERM_SLUG_MAX_LENGTH, validators=[topic_v2_exists]),
    )
    cover = RestrictedImageFileSizeField(
        allow_empty_file=False,
        allow_null=True,
        required=False,
        max_upload_size=settings.COMMUNITY_COVER_MAX_SIZE,
    )
    avatar = RestrictedImageFileSizeField(
        allow_empty_file=False,
        allow_null=True,
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
        allow_blank=True,
    )
    geolocation = GeolocationPointSerializer(
        required=False,
    )
    contact_description = serializers.CharField(
        required=False,
        max_length=settings.COMMUNITY_CONTACT_DESCRIPTION_MAX_LENGTH,
        allow_blank=True,
        validators=[sanitize_text],
    )
    contact_email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    contact_phone = serializers.CharField(
        required=False,
        max_length=settings.COMMUNITY_CONTACT_PHONE_MAX_LENGTH,
        allow_blank=True,
    )
    onboarding_steps = serializers.ListField(
        required=False,
        child=UpdateOnboardingStepSerializer(),
    )


class InviteToCommunityByEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    space_id = serializers.UUIDField(
        validators=[community_id_exists],
        required=True,
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


class AddCollaborationToolSerializer(serializers.Serializer):
    space_id = serializers.UUIDField(
        validators=[community_id_exists],
        required=True,
    )
    url = serializers.URLField(
        max_length=settings.COLLABORATION_TOOL_URL_MAX_LENGTH,
        validators=[url_safety_validator],
        required=True,
    )
    title = serializers.CharField(
        min_length=settings.COLLABORATION_TOOL_TITLE_MIN_LENGTH,
        max_length=settings.COLLABORATION_TOOL_TITLE_MAX_LENGTH,
        required=True,
    )
    description = serializers.CharField(
        min_length=settings.COLLABORATION_TOOL_DESCRIPTION_MIN_LENGTH,
        max_length=settings.COLLABORATION_TOOL_DESCRIPTION_MAX_LENGTH,
        required=False,
        allow_blank=True,
        validators=[sanitize_text],
    )
    collection_type = serializers.ChoiceField(
        allow_blank=False, required=False, choices=CollaborationTool.CollectionType.choices
    )
    thumbnail = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.TASK_THUMBNAIL_MAX_SIZE,
    )


class UpdateCollaborationToolSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        validators=[collaboration_tool_id_exists],
        required=True,
    )
    url = serializers.URLField(
        max_length=settings.COLLABORATION_TOOL_URL_MAX_LENGTH,
        validators=[url_safety_validator],
        required=False,
    )
    title = serializers.CharField(
        min_length=settings.COLLABORATION_TOOL_TITLE_MIN_LENGTH,
        max_length=settings.COLLABORATION_TOOL_TITLE_MAX_LENGTH,
        required=False,
    )
    description = serializers.CharField(
        min_length=settings.COLLABORATION_TOOL_DESCRIPTION_MIN_LENGTH,
        max_length=settings.COLLABORATION_TOOL_DESCRIPTION_MAX_LENGTH,
        required=False,
        allow_blank=True,
        validators=[sanitize_text],
    )
    collection_type = serializers.ChoiceField(required=False, choices=CollaborationTool.CollectionType.choices)
    thumbnail = RestrictedImageFileSizeField(
        allow_empty_file=False,
        allow_null=True,
        required=False,
        max_upload_size=settings.TASK_THUMBNAIL_MAX_SIZE,
    )


class CreateTaskSerializer(serializers.Serializer):
    space_id = serializers.UUIDField(
        validators=[community_id_exists],
        required=True,
    )
    name = serializers.CharField(
        min_length=settings.TASK_NAME_MIN_LENGTH,
        max_length=settings.TASK_NAME_MAX_LENGTH,
        required=True,
    )
    description = serializers.CharField(
        max_length=settings.TASK_DESCRIPTION_MAX_LENGTH, required=True, validators=[sanitize_text]
    )
    slots_available = serializers.IntegerField(required=True, max_value=600)
    location = serializers.CharField(
        max_length=settings.TASK_LOCATION_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )
    geolocation = GeolocationPointSerializer(required=False)
    visibility = serializers.ChoiceField(required=True, choices=VisibilityType.choices)
    location_type = serializers.ChoiceField(required=True, choices=Task.LocationType.choices)
    regularity = serializers.ChoiceField(required=False, choices=Task.Regularity.choices)
    # make duration required after FE clients that don't send this for updates/creation of task are phased out (1.54+?)
    duration = serializers.ChoiceField(required=False, choices=Task.Duration.choices)
    timeframe_start_date = serializers.DateField(required=False)
    timeframe_end_date = serializers.DateField(required=False)
    contact_email = serializers.EmailField(
        required=True,
    )
    contact_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=settings.TASK_CONTACT_PHONE_MAX_LENGTH,
    )
    skills = serializers.ListField(
        min_length=settings.TASK_SKILLS_MIN_AMOUNT,
        max_length=settings.TASK_SKILLS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[skill_with_id_exists]),
    )
    skills_v2 = serializers.ListField(
        min_length=settings.TASK_SKILLS_MIN_AMOUNT,
        max_length=settings.TASK_SKILLS_MAX_AMOUNT,
        required=False,
        child=serializers.CharField(max_length=settings.TERM_SLUG_MAX_LENGTH, validators=[skill_v2_exists]),
    )
    thumbnail = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.TASK_THUMBNAIL_MAX_SIZE,
    )
    remove_thumbnail = serializers.BooleanField(default=False)

    def validate(self, data):
        if "timeframe_start_date" not in data and "timeframe_end_date" not in data:
            return data

        if "timeframe_start_date" not in data and "timeframe_end_date" in data:
            raise serializers.ValidationError("Timeframe incomplete start missing")

        if "timeframe_start_date" in data and "timeframe_end_date" not in data:
            raise serializers.ValidationError("Timeframe incomplete end missing")

        if data["timeframe_end_date"] < data["timeframe_start_date"]:
            raise serializers.ValidationError("Timeframe end must occur after start")

        return data


class UpdateTaskSerializer(serializers.Serializer):
    task_id = serializers.UUIDField(
        validators=[task_id_exists],
        required=True,
    )
    space_id = serializers.UUIDField(
        validators=[community_id_exists],
        required=True,
    )
    name = serializers.CharField(
        min_length=settings.TASK_NAME_MIN_LENGTH,
        max_length=settings.TASK_NAME_MAX_LENGTH,
        required=True,
    )
    description = serializers.CharField(
        max_length=settings.TASK_DESCRIPTION_MAX_LENGTH, required=True, validators=[sanitize_text]
    )
    slots_available = serializers.IntegerField(required=False, max_value=600)
    location = serializers.CharField(
        max_length=settings.TASK_LOCATION_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )
    geolocation = GeolocationPointSerializer(required=False)
    visibility = serializers.ChoiceField(required=True, choices=VisibilityType.choices)
    location_type = serializers.ChoiceField(required=True, choices=Task.LocationType.choices)
    regularity = serializers.ChoiceField(required=False, choices=Task.Regularity.choices)
    # make duration required after FE clients that don't send this for updates/creation of task are phased out (1.54+?)
    duration = serializers.ChoiceField(required=False, choices=Task.Duration.choices)
    timeframe_start_date = serializers.DateField(required=False)
    timeframe_end_date = serializers.DateField(required=False)
    contact_email = serializers.EmailField(
        required=True,
    )
    contact_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=settings.TASK_CONTACT_PHONE_MAX_LENGTH,
    )
    skills = serializers.ListField(
        min_length=settings.TASK_SKILLS_MIN_AMOUNT,
        max_length=settings.TASK_SKILLS_MAX_AMOUNT,
        required=False,
        child=serializers.UUIDField(validators=[skill_with_id_exists]),
    )
    skills_v2 = serializers.ListField(
        min_length=settings.TASK_SKILLS_MIN_AMOUNT,
        max_length=settings.TASK_SKILLS_MAX_AMOUNT,
        required=False,
        allow_empty=True,
        child=serializers.CharField(max_length=settings.TERM_SLUG_MAX_LENGTH, validators=[skill_v2_exists]),
    )
    thumbnail = RestrictedImageFileSizeField(
        allow_empty_file=False,
        allow_null=True,
        required=False,
        max_upload_size=settings.TASK_THUMBNAIL_MAX_SIZE,
    )


class AddExternalLinkSerializer(serializers.Serializer):
    space_id = serializers.UUIDField(
        validators=[community_id_exists],
        required=True,
    )
    url = serializers.URLField(
        max_length=settings.EXTERNAL_LINK_URL_MAX_LENGTH,
        validators=[url_safety_validator],
        required=False,
    )
    type = serializers.ChoiceField(required=False, choices=ExternalLinkType.choices)
    name = serializers.CharField(
        max_length=settings.EXTERNAL_LINK_NAME_MAX_LENGTH,
        required=True,
        allow_blank=False,
    )


class UpdateExternalLinkSerializer(serializers.Serializer):
    id = serializers.UUIDField(
        validators=[external_link_id_exists],
        required=True,
    )
    url = serializers.URLField(
        max_length=settings.EXTERNAL_LINK_URL_MAX_LENGTH,
        validators=[url_safety_validator],
        required=False,
    )
    type = serializers.ChoiceField(required=False, choices=ExternalLinkType.choices)
    name = serializers.CharField(
        max_length=settings.EXTERNAL_LINK_NAME_MAX_LENGTH,
        required=True,
        allow_blank=False,
    )
