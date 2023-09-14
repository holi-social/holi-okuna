from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from openbook_auth.forms import UserProfileFormSet
from openbook_auth.models import User, UserProfile


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
    list_display = ("username", "email", "get_first_name", "get_last_name", "get_location", "date_joined", "identity")
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

    def has_add_permission(self, request, obj=None):
        return False
