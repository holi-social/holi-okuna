from django.contrib import admin

from openbook_communities.models import Community


class CommunityAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return True # needs to be true for adding communities via /admin (needed for creating posts)


admin.site.register(Community, CommunityAdmin)
