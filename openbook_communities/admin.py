from typing import cast
from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder
from openbook_auth.models import User
from openbook_communities.events import (
    publish_task_created_event,
    publish_task_updated_event,
    publish_task_deleted_event,
    publish_space_deleted_event,
)
from openbook_communities.events import (
    publish_space_created_event,
    publish_space_updated_event,
    publish_space_user_added_event,
)
from openbook_communities.models import (
    CollaborationTool,
    Community,
    CommunityMembership,
    ExternalLink,
    Task,
    OnboardingStep,
)
from openbook_communities.models.network_relationship import SpacesRelationship
from django.db.models import Count

import traceback
import structlog
import time


logger = structlog.get_logger(__name__)


class CommunityNetworkRelationshipInline(admin.TabularInline):
    model = SpacesRelationship
    fk_name = "from_space"
    min_num = 0
    max_num = 1
    extra = 0

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("from_space")


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    readonly_fields = ["name"]
    list_display = ("name", "title", "id", "creator", "created", "get_num_posts", "get_num_members", "is_deleted")
    search_fields = ("id", "title", "creator__email", "creator__profile__name", "creator__profile__last_name")
    exclude = ["banned_users", "starrers", "geolocation_geojson"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(num_posts=Count("posts"), num_members=Count("memberships"))

    inlines = [CommunityNetworkRelationshipInline]

    @admin.display(description="Num posts")
    def get_num_posts(self, obj):
        return obj.num_posts

    @admin.display(description="Num members")
    def get_num_members(self, obj):
        return obj.num_members

    def has_add_permission(self, request, obj=None):
        return True  # needs to be true for adding communities via /admin (needed for creating posts)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            CommunityMembership.create_membership(
                user=obj.creator, is_administrator=True, is_moderator=False, community=obj
            )
        try:
            if not change:
                # This is a new instance
                publish_space_created_event(obj)
            else:
                # This is an existing instance being updated
                publish_space_updated_event(obj)

                tasks = list(Task.objects.filter(deleted_at=None, community_id=obj.id).all())
                for task in tasks:
                    publish_task_updated_event(request.user, task)

        except Exception as e:
            # Log the error but don't break the delete operation
            logger.error(f"Failed to publish space event: {e}")
            logger.error(traceback.format_exc())

    def delete_model(self, request, obj):
        try:
            # Fetch tasks while they still exist - before actually deleting the space
            tasks = list(Task.objects.filter(deleted_at=None, community_id=obj.id).all())

            super().delete_model(request, obj)

            for task in tasks:
                publish_task_deleted_event(request.user, task)
            publish_space_deleted_event(obj)
        except Exception as e:
            # Log the error but don't break the delete operation
            logger.error(f"Failed to publish space or task deleted event: {e}")
            logger.error(traceback.format_exc())

    @admin.action(description="Resend SpaceCreatedEvent")
    def resend_space_created_event(self, request, queryset):
        for community in queryset.all():
            logger.info("Resending SpaceCreatedEvent: " + str(community))
            try:
                publish_space_created_event(community)
                time.sleep(2)
                for membership in community.memberships.all():
                    logger.info("Adding user: " + str(membership.user))
                    publish_space_user_added_event(membership.user.username, community)
            except Exception:
                logger.warning(traceback.format_exc())

    @admin.action(description="Resend SpaceUpdatedEvent")
    def resend_space_updated_event(self, request, queryset):
        for community in queryset.all():
            logger.info("Resending SpaceUpdatedEvent: " + str(community))
            try:
                publish_space_updated_event(community)
            except Exception:
                logger.warning(traceback.format_exc())

    actions = [resend_space_created_event, resend_space_updated_event]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        def nice_name(obj):
            return f"{obj.profile.name if hasattr(obj, 'profile') else ''} {obj.profile.last_name if hasattr(obj, 'profile') else ''} ({obj.email}), {obj.username}"

        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "creator":
            formfield.label_from_instance = nice_name
        return formfield


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "community", "user", "is_administrator", "created")
    list_filter = ("is_administrator", ("created", DateRangeQuickSelectListFilterBuilder(title="Created")))
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
    exclude = ["geolocation_geojson"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            if not change:
                # This is a new instance
                publish_task_created_event(cast(User, request.user), obj)
            else:
                # This is an existing instance being updated
                publish_task_updated_event(cast(User, request.user), obj)

        except Exception as e:
            # Log the error but don't break the save operation
            logger.error(f"Failed to publish task event: {e}")
            logger.error(traceback.format_exc())

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        try:
            publish_task_deleted_event(cast(User, request.user), obj)
        except Exception as e:
            # Log the error but don't break the delete operation
            logger.error(f"Failed to publish task deleted event: {e}")
            logger.error(traceback.format_exc())


@admin.register(OnboardingStep)
class CommunityOnboardingStepAdmin(admin.ModelAdmin):
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
