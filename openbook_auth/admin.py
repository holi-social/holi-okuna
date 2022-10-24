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
    search_fields = ('username', 'email', 'full_name')

    exclude = ('password',)
    list_display = ('username', 'email', 'full_name')

    def full_name(self, object):
        if object.profile.name is None:
            return None
        else:
            if object.profile.last_name is None or object.profile.last_name == '':
                return object.profile.name
            else:
                return f"{object.profile.name} {object.profile.last_name}"

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(User, UserAdmin)
