from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

import strawberry

from openbook_auth.models import User
from openbook_common.models import ModelWithUUID
from openbook_communities.models import Community


class Device(ModelWithUUID):
    @strawberry.enum
    class DeviceType(models.TextChoices):
        ANDROID = ("ANDROID",)
        IOS = ("IOS",)

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices", null=False)
    token = models.CharField(
        _("token"),
        null=False,
        editable=False,
        unique=False,
        max_length=settings.DEVICE_TOKEN_MAX_LENGTH,
    )
    created = models.DateTimeField(editable=False)
    device_type = models.CharField(
        max_length=10,
        choices=DeviceType.choices,
        default=DeviceType.IOS,
        blank=False,
        null=False,
    )

    class Meta:
        unique_together = ("owner", "token", "device_type")

    @classmethod
    def create_device(cls, owner, token, device_type):
        device = cls.objects.create(owner=owner, token=token, device_type=device_type)

        return device

    def save(self, *args, **kwargs):
        if not self.created:
            self.created = timezone.now()
        return super(Device, self).save(*args, **kwargs)
