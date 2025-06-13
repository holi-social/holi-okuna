import traceback

from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from openbook_auth.events import (
    publish_user_name_updated_event,
    publish_user_updated_event,
    publish_user_deleted_event,
)
from openbook_auth.forms import UserProfileFormSet
from openbook_auth.models import User, UserProfile
import structlog

logger = structlog.get_logger(__name__)


class UserProfileInline(admin.TabularInline):
    model = UserProfile
    formset = UserProfileFormSet

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    inlines = [
        UserProfileInline,
    ]

    exclude = ("password",)
    list_display = (
        "username",
        "email",
        "get_first_name",
        "get_last_name",
        "get_location",
        "date_joined",
        "identity",
        "role",
        "is_deleted",
        "is_verified",
    )
    list_filter = (("date_joined", DateRangeQuickSelectListFilterBuilder(title="Date joined")),)
    search_fields = ("username", "email", "identity", "profile__name", "profile__last_name")

    @admin.display(ordering="profile__name", description="First name")
    def get_first_name(self, obj):
        return obj.profile.name if hasattr(obj, "profile") else None

    @admin.display(ordering="profile__last_name", description="Last name")
    def get_last_name(self, obj):
        return obj.profile.last_name if hasattr(obj, "profile") else None

    @admin.display(ordering="profile__location", description="Location")
    def get_location(self, obj):
        return obj.profile.location if hasattr(obj, "profile") else None

    @admin.action(description="Resend UserNameUpdatedEvent")
    def resend_user_name_updated_event(self, request, queryset):
        for user in queryset.all():
            if user.identity and user.profile:
                try:
                    publish_user_name_updated_event(user)
                except Exception as e:
                    logger.warning("Failed to resend event for user %s: %s", user.id, e)
                    logger.warning(traceback.format_exc())

    actions = [resend_user_name_updated_event]

    def has_add_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            publish_user_updated_event(obj)
        except Exception as e:
            # Log the error but don't break the save operation
            logger.error(f"Failed to publish user updated event: {e}")
            logger.error(traceback.format_exc())

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        try:
            publish_user_deleted_event(obj)
        except Exception as e:
            # Log the error but don't break the delete operation
            logger.error(f"Failed to publish user deleted event: {e}")
            logger.error(traceback.format_exc())
