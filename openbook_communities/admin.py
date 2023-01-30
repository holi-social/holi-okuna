from django.contrib import admin

from openbook_communities.models import (
    Community,
    CommunityMembership,
    Task,
    ExternalLink,
)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "created")

    def has_add_permission(self, request, obj=None):
        return True  # needs to be true for adding communities via /admin (needed for creating posts)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            CommunityMembership.create_membership(
                user=obj.creator, is_administrator=True, is_moderator=False, community=obj
            )


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user")


@admin.register(Task)
class CommunityTaskAdmin(admin.ModelAdmin):
    model = Task
    list_display = ("community", "name", "location", "creator", "created")


@admin.register(ExternalLink)
class CommunityLinkAdmin(admin.ModelAdmin):
    list_display = ("community", "type", "url")
