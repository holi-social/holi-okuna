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
        if change:
            super().save_model(request, obj, form, change)
        else:
            Community.create_community(
                obj.name,
                obj.title,
                obj.creator,
                obj.color,
                obj.type,
                obj.user_adjective,
                obj.users_adjective,
                obj.avatar,
                obj.cover,
                obj.description,
                obj.rules,
                invites_enabled=obj.invites_enabled,
                location=obj.location,
            )


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user")
    pass


@admin.register(Task)
class CommunityTaskAdmin(admin.ModelAdmin):
    model = Task
    list_display = ("community", "name", "location", "creator", "created")


@admin.register(ExternalLink)
class CommunityLinkAdmin(admin.ModelAdmin):
    list_display = ("community", "type", "url")
