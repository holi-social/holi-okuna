from django.conf import settings
from rest_framework import serializers

from openbook_devices.models import Device


class RegisterDeviceSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=settings.DEVICE_TOKEN_MAX_LENGTH,
        required=True,
        allow_blank=False,
    )
    device_type = serializers.ChoiceField(required=True, allow_blank=False, choices=Device.DeviceType.choices)
