from django.contrib import admin

from openbook_communities.models import (
    CollaborationTool,
    Community,
    CommunityMembership,
    ExternalLink,
    Task,
    OnboardingStep,
)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    readonly_fields = ["name"]
    list_display = ("name", "title", "creator", "created", "get_num_posts", "get_num_members")
    search_fields = ("title", "creator__email", "creator__profile__name", "creator__profile__last_name")

    @admin.display(description="Num posts")
    def get_num_posts(self, obj):
        return obj.posts.count()

    @admin.display(description="Num members")
    def get_num_members(self, obj):
        return obj.memberships.count()

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
    list_display = ("id", "community", "user", "is_administrator")
    list_filter = ("is_administrator",)
    search_fields = ("community__title", "community__creator__email", "user__email")


@admin.register(Task)
class CommunityTaskAdmin(admin.ModelAdmin):
    model = Task
    list_display = (
        "community",
        "name",
        "description",
        "visibility",
        "location_type",
        "location",
        "geolocation",
        "creator",
        "created",
        "contact_email",
        "contact_phone",
        "thumbnail",
        "regularity",
        "slots_taken",
        "slots_available",
    )


@admin.register(OnboardingStep)
class CommunityTaskAdmin(admin.ModelAdmin):
    model = OnboardingStep
    list_display = (
        "community",
        "id",
        "step_number",
        "text",
    )


@admin.register(ExternalLink)
class CommunityLinkAdmin(admin.ModelAdmin):
    list_display = ("community", "type", "url")


@admin.register(CollaborationTool)
class CommunityCollaborationToolAdmin(admin.ModelAdmin):
    list_display = ("url", "domain", "title", "collection_type", "description")
