from django.contrib import admin

# RegisterView your models here.
from openbook_auth.models import User, UserProfile


class UserProfileInline(admin.TabularInline):
    model = UserProfile

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
        return (
            " ".join(filter(None, [object.profile.name, object.profile.last_name]))
            or None  # map empty string to None
        )

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(User, UserAdmin)
