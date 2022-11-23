from django.contrib import admin

from openbook_communities.models import Community, CommunityMembership


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    def has_add_permission(self, request, obj=None):
        return True  # needs to be true for adding communities via /admin (needed for creating posts)


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    pass
