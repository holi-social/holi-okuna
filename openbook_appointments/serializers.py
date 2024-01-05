from rest_framework import serializers

from openbook import settings
from openbook_appointments.enums import PermissionType
from openbook_appointments.validators import space_member_exists, appointment_exists
from openbook_common.serializers import GeolocationPointSerializer
from openbook_common.serializers_fields.request import RestrictedImageFileSizeField
from openbook_communities.validators import community_id_exists


class CreateAppointmentSerializer(serializers.Serializer):
    title = serializers.CharField(
        min_length=settings.APPOINTMENT_TITLE_MIN_LENGTH,
        max_length=settings.APPOINTMENT_TITLE_MAX_LENGTH,
        required=True,
    )

    invite_only = serializers.BooleanField(required=True)

    participant_ids = serializers.ListField(
        required=False,
        child=serializers.UUIDField(validators=[space_member_exists]),
    )

    start_date_time = serializers.DateTimeField(required=True)

    end_date_time = serializers.DateTimeField(required=True)

    location = serializers.CharField(
        max_length=settings.APPOINTMENT_LOCATION_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )

    geolocation = GeolocationPointSerializer(required=False, allow_null=True)

    description = serializers.CharField(
        max_length=settings.TASK_DESCRIPTION_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )

    thumbnail = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.TASK_THUMBNAIL_MAX_SIZE,
    )

    permission = serializers.ChoiceField(required=True, choices=PermissionType.choices)

    space_id = serializers.UUIDField(
        validators=[community_id_exists],
        required=True,
    )

    video_call_link = serializers.URLField(
        min_length=settings.VIDEO_CALL_LINK_URL_MIN_LENGTH,
        max_length=settings.VIDEO_CALL_LINK_URL_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )

    video_call_info = serializers.CharField(
        max_length=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH,
        required=False,
        allow_blank=True,
    )


class UpdateAppointmentSerializer(serializers.Serializer):
    appointment_id = serializers.UUIDField(
        validators=[appointment_exists],
        required=True,
    )

    title = serializers.CharField(
        min_length=settings.APPOINTMENT_TITLE_MIN_LENGTH,
        max_length=settings.APPOINTMENT_TITLE_MAX_LENGTH,
        required=False,
    )

    invite_only = serializers.BooleanField(required=False)

    participant_ids = serializers.ListField(
        required=False,
        child=serializers.UUIDField(validators=[space_member_exists]),
    )

    start_date_time = serializers.DateTimeField(required=False)

    end_date_time = serializers.DateTimeField(required=False)

    location = serializers.CharField(
        max_length=settings.APPOINTMENT_LOCATION_MAX_LENGTH,
        required=False,
    )

    geolocation = GeolocationPointSerializer(required=False)

    description = serializers.CharField(
        max_length=settings.TASK_DESCRIPTION_MAX_LENGTH,
        required=False,
    )

    thumbnail = RestrictedImageFileSizeField(
        allow_empty_file=False,
        required=False,
        max_upload_size=settings.TASK_THUMBNAIL_MAX_SIZE,
    )

    permission = serializers.ChoiceField(required=False, choices=PermissionType.choices)

    video_call_link = serializers.URLField(
        min_length=settings.VIDEO_CALL_LINK_URL_MIN_LENGTH,
        max_length=settings.VIDEO_CALL_LINK_URL_MAX_LENGTH,
        required=False,
    )

    video_call_info = serializers.CharField(
        max_length=settings.VIDEO_CALL_LINK_DESCRIPTION_MAX_LENGTH,
        required=False,
    )
