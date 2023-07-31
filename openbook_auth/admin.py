from django.contrib import admin

from openbook_auth.forms import UserProfileFormSet
from openbook_auth.models import User, UserProfile


class UserProfileInline(admin.TabularInline):
    model = UserProfile
    formset = UserProfileFormSet

    def has_delete_permission(self, request, obj=None):
        return False


class UserAdmin(admin.ModelAdmin):
    inlines = [
        UserProfileInline,
    ]
    search_fields = ("username", "email")

    exclude = ("password",)
    list_display = ("username", "email", "full_name")

    def full_name(self, object):
        return object.profile.full_name() if hasattr(object, "profile") else None

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(User, UserAdmin)
