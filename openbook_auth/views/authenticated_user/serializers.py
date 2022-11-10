from rest_framework import serializers
from django.conf import settings
from django.utils.translation import gettext as _

from openbook.settings import (
    USERNAME_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PROFILE_AVATAR_URL_MAX_LENGTH,
    PROFILE_COVER_URL_MAX_LENGTH,
    PROFILE_NAME_MAX_LENGTH,
)
from openbook_auth.models import User, UserProfile, EngagementLevelChoice
from openbook_auth.validators import (
    username_characters_validator,
    email_not_taken_validator,
    interests_json_validator,
    skills_json_validator,
    sdgs_json_validator,
)
from django.contrib.auth.password_validation import validate_password

from openbook_common.models import Badge, Language
from openbook_common.serializers_fields.request import (
    FriendlyUrlField,
    RestrictedImageFileSizeField,
)
from openbook_common.serializers_fields.user import (
    FollowersCountField,
    FollowingCountField,
    IsMemberOfCommunities,
    UnreadNotificationsCountField,
    IsGlobalModeratorField,
    UserPostsCountField,
)
from openbook_common.validators import name_characters_validator, language_id_exists
from openbook_moderation.serializers_fields.user import (
    UserPendingCommunitiesModeratedObjectsCountField,
    UserActiveModerationPenaltiesCountField,
)


class GetAuthenticatedUserProfileBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("keyword", "keyword_description")


class GetAuthenticatedUserProfileSerializer(serializers.ModelSerializer):
    badges = GetAuthenticatedUserProfileBadgeSerializer(many=True)

    class Meta:
        model = UserProfile
        fields = (
            "id",
            "name",
            "avatar",
            "about_me",
            "url",
            "location",
            "cover",
            "is_of_legal_age",
            "followers_count_visible",
            "community_posts_visible",
            "badges",
            "last_name",
            "pronouns",
            "engagement_level",
            "interests",
            "sdgs",
            "skills",
        )


class UserLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = (
            "id",
            "code",
            "name",
        )


class GetAuthenticatedUserSerializer(serializers.ModelSerializer):
    profile = GetAuthenticatedUserProfileSerializer(many=False)
    unread_notifications_count = UnreadNotificationsCountField()
    followers_count = FollowersCountField()
    is_global_moderator = IsGlobalModeratorField()
    following_count = FollowingCountField()
    is_member_of_communities = IsMemberOfCommunities()
    pending_communities_moderated_objects_count = (
        UserPendingCommunitiesModeratedObjectsCountField()
    )
    active_moderation_penalties_count = UserActiveModerationPenaltiesCountField()
    language = UserLanguageSerializer()

    class Meta:
        model = User
        fields = (
            "id",
            "uuid",
            "email",
            "username",
            "avatar_default_color",
            "avatar_label",
            "profile",
            "language",
            "invite_count",
            "date_joined",
            "are_guidelines_accepted",
            "followers_count",
            "following_count",
            "connections_circle_id",
            "is_member_of_communities",
            "is_global_moderator",
            "unread_notifications_count",
            "pending_communities_moderated_objects_count",
            "active_moderation_penalties_count",
            "visibility",
        )


class LegacyGetAuthenticatedUserSerializer(serializers.ModelSerializer):
    profile = GetAuthenticatedUserProfileSerializer(many=False)
    unread_notifications_count = UnreadNotificationsCountField()
    followers_count = FollowersCountField()
    is_global_moderator = IsGlobalModeratorField()
    posts_count = UserPostsCountField()
    following_count = FollowingCountField()
    is_member_of_communities = IsMemberOfCommunities()
    pending_communities_moderated_objects_count = (
        UserPendingCommunitiesModeratedObjectsCountField()
    )
    active_moderation_penalties_count = UserActiveModerationPenaltiesCountField()
    language = UserLanguageSerializer()

    class Meta:
        model = User
        fields = (
            "id",
            "uuid",
            "email",
            "username",
            "profile",
            "language",
            "invite_count",
            "date_joined",
            "posts_count",
            "are_guidelines_accepted",
            "followers_count",
            "following_count",
            "connections_circle_id",
            "is_member_of_communities",
            "is_global_moderator",
            "unread_notifications_count",
            "pending_communities_moderated_objects_count",
            "active_moderation_penalties_count",
            "visibility",
        )


class UpdateAuthenticatedUserSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=USERNAME_MAX_LENGTH,
        allow_blank=False,
        validators=[username_characters_validator],
        required=False,
    )
    avatar = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        allow_null=True,
        max_upload_size=settings.PROFILE_AVATAR_MAX_SIZE,
    )
    cover = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        allow_null=True,
        max_upload_size=settings.PROFILE_COVER_MAX_SIZE,
    )
    password = serializers.CharField(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        validators=[validate_password],
        required=False,
        allow_blank=False,
    )
    name = serializers.CharField(
        max_length=PROFILE_NAME_MAX_LENGTH,
        required=False,
        allow_blank=False,
        validators=[name_characters_validator],
    )
    followers_count_visible = serializers.BooleanField(
        required=False, default=None, allow_null=True
    )
    community_posts_visible = serializers.BooleanField(
        required=False, default=None, allow_null=True
    )
    about_me = serializers.CharField(
        max_length=settings.PROFILE_ABOUT_ME_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )
    url = FriendlyUrlField(required=False, allow_blank=True)
    location = serializers.CharField(
        max_length=settings.PROFILE_LOCATION_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )
    visibility = serializers.ChoiceField(choices=User.VISIBILITY_TYPES, required=False)

    last_name = serializers.CharField(
        max_length=settings.PROFILE_LAST_NAME_MAX_LENGTH,
        allow_blank=True,
        validators=[name_characters_validator],
        required=False,
    )
    pronouns = serializers.CharField(
        max_length=settings.PROFILE_PRONOUNS_MAX_LENGTH,
        allow_blank=True,
        validators=[],
        required=False,
    )
    engagement_level = serializers.ChoiceField(
        choices=EngagementLevelChoice.choices, required=False, allow_blank=True
    )

    interests = serializers.JSONField(
        required=False, validators=[interests_json_validator]
    )
    sdgs = serializers.JSONField(required=False, validators=[sdgs_json_validator])
    skills = serializers.JSONField(required=False, validators=[skills_json_validator])


class DeleteAuthenticatedUserSerializer(serializers.Serializer):
    password = serializers.CharField(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        validators=[validate_password],
        required=True,
        allow_blank=False,
    )


class UpdateAuthenticatedUserSettingsSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        validators=[validate_password],
        required=False,
        allow_blank=False,
    )
    current_password = serializers.CharField(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        validators=[validate_password],
        required=False,
        allow_blank=False,
    )
    email = serializers.EmailField(
        validators=[email_not_taken_validator], required=False
    )

    def validate(self, data):
        if "new_password" not in data and "current_password" in data:
            raise serializers.ValidationError(
                _("New password must be supplied together with the current password")
            )

        if "new_password" in data and "current_password" not in data:
            raise serializers.ValidationError(
                _("Current password must be supplied together with the new password")
            )

        return data


class AuthenticatedUserLanguageSerializer(serializers.Serializer):
    language_id = serializers.UUIDField(validators=[language_id_exists], required=True)


class AuthenticatedUserAllLanguagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = (
            "id",
            "code",
            "name",
        )
