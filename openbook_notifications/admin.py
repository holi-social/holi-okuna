from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet

from openbook_notifications.models import (
    CommunityNewPostNotification,
    CommunityAdminPrivilegesGrantedNotification,
    CommunityAdminPrivilegesRevokedNotification,
    CommunityMembershipRevokedNotification,
)
from openbook_notifications.models.release_notification import ReleaseNotification


# Register your models here.
@admin.register(ReleaseNotification)
class ReleaseNotificationAdmin(ModelAdmin):
    list_display = ("order", "id", "post", "is_sent")
    readonly_fields = ("is_sent",)
    actions = ["send"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "post":
            formfield.label_from_instance = lambda obj: f"{obj.title} ({obj.creator.email})"
        return formfield

    def send(self, request, queryset: QuerySet[ReleaseNotification]):
        for notification in queryset.all():
            if not notification.is_sent:
                notified_users = notification.send_to_all_users()

                messages.info(
                    request, f"Notification for Post {notification.post.title} sent to {notified_users} Users"
                )
            else:
                messages.warning(
                    request, f"Notification for Post {notification.post.title} has already been sent, ignoring"
                )


@admin.register(CommunityNewPostNotification)
class CommunityNewPostNotificationAdmin(ModelAdmin):
    list_display = ("id", "post", "teaser", "post_created")

    @admin.display(description="Post created")
    def post_created(self, obj):
        return obj.post.created


@admin.register(CommunityAdminPrivilegesGrantedNotification)
class CommunityAdminPrivilegesGrantedNotificationAdmin(ModelAdmin):
    list_display = ("id", "granted_user", "community", "created")

    @admin.display(description="Notification created")
    def created(self, obj):
        return obj.notification.first().created if obj.notification.first() else None


@admin.register(CommunityAdminPrivilegesRevokedNotification)
class CommunityAdminPrivilegesRevokedNotificationAdmin(ModelAdmin):
    list_display = ("id", "revoked_user", "community", "created")

    @admin.display(description="Notification created")
    def created(self, obj):
        return obj.notification.first().created if obj.notification.first() else None


@admin.register(CommunityMembershipRevokedNotification)
class CommunityMembershipRevokedNotificationAdmin(ModelAdmin):
    list_display = ("id", "revoked_user", "community", "created")

    @admin.display(description="Notification created")
    def created(self, obj):
        return obj.notification.first().created if obj.notification.first() else None
