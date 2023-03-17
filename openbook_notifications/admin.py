import json
import logging

from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet

from openbook_notifications.models.release_notification import ReleaseNotification

logger = logging.getLogger(__name__)

# Register your models here.
@admin.register(ReleaseNotification)
class ReleaseNotificationAdmin(ModelAdmin):
    list_display = ("order", "id", "post", "is_sent")
    readonly_fields = ("is_sent",)
    actions = ["send"]

    def send(self, request, queryset: QuerySet[ReleaseNotification]):
        for notification in queryset.all():
            if not notification.is_sent:
                notification.send_to_all_users()

                messages.info(request, f"HALLOOOOO {notification.get_options()} wasSent: {notification.is_sent}")
            else:
                messages.error(request, f"Notification {notification.id} has already been sent, ignoring")
