from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from openbook.settings import (
    USERNAME_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    PROFILE_NAME_MAX_LENGTH,
)
from openbook_auth.models import User, EngagementLevelChoice
from openbook_auth.validators import (
    username_characters_validator,
    interest_with_id_exists,
    skill_with_id_exists,
    sdg_with_id_exists,
    identity_characters_validator,
)
from openbook_common.serializers import GeolocationFeatureSerializer
from openbook_common.serializers_fields.request import (
    FriendlyUrlField,
    RestrictedImageFileSizeField,
)
from openbook_common.validators import (
    name_characters_validator,
    sanitize_text,
    url_safety_validator,
    topic_v2_exists,
    skill_v2_exists,
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
    followers_count_visible = serializers.BooleanField(required=False, default=None, allow_null=True)
    community_posts_visible = serializers.BooleanField(required=False, default=None, allow_null=True)
    about_me = serializers.CharField(
        max_length=settings.PROFILE_ABOUT_ME_MAX_LENGTH, required=False, allow_blank=True, validators=[sanitize_text]
    )
    url = FriendlyUrlField(required=False, allow_blank=True, validators=[url_safety_validator])
    location = serializers.CharField(
        max_length=settings.PROFILE_LOCATION_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )
    geolocation = GeolocationFeatureSerializer(required=False)
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
    engagement_level = serializers.ChoiceField(choices=EngagementLevelChoice.choices, required=False, allow_blank=True)

    interests = serializers.ListField(
        required=False,
        allow_empty=True,
        child=serializers.UUIDField(validators=[interest_with_id_exists]),
    )
    interests_v2 = serializers.ListField(
        required=False,
        allow_empty=True,
        child=serializers.CharField(max_length=settings.TERM_SLUG_MAX_LENGTH, validators=[topic_v2_exists]),
    )
    sdgs = serializers.ListField(
        required=False,
        allow_empty=True,
        child=serializers.UUIDField(validators=[sdg_with_id_exists]),
    )
    skills = serializers.ListField(
        required=False,
        allow_empty=True,
        child=serializers.UUIDField(validators=[skill_with_id_exists]),
    )
    skills_v2 = serializers.ListField(
        required=False,
        allow_empty=True,
        child=serializers.CharField(max_length=settings.TERM_SLUG_MAX_LENGTH, validators=[skill_v2_exists]),
    )
    identity = serializers.CharField(
        min_length=1,
        max_length=settings.IDENTITY_MAX_LENGTH,
        validators=[identity_characters_validator],
        required=False,
        allow_blank=True,
    )
    tracking_consent_analytics = serializers.BooleanField(required=False, default=None, allow_null=True)
    tracking_consent_personalization = serializers.BooleanField(required=False, default=None, allow_null=True)
