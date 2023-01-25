from django.contrib import admin
from django.contrib.admin import ModelAdmin
from modeltranslation.admin import TranslationAdmin

from openbook_moderation.models import (
    ModerationCategory,
    ModerationReport,
    ModeratedObject,
)


class ModerationCategoryAdmin(TranslationAdmin):
    def has_add_permission(self, request):
        return True

    def has_delete_permission(self, request, obj=None):
        return True


admin.site.register(ModerationCategory, ModerationCategoryAdmin)


class ModerationReportAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    readonly_fields = ["reporter", "moderated_object", "category", "description"]


admin.site.register(ModerationReport, ModerationReportAdmin)


class ModeratedObjectAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    list_display = ("id", "object_type", "object", "status", "verified")
    readonly_fields = [
        "verified",
        "category",
        "description",
        "community",
        "status",
        "object_type",
        "object_id",
        "content_type",
    ]

    @admin.display(description="Content")
    def object(self, obj):
        match obj.object_type:
            case ModeratedObject.OBJECT_TYPE_POST:
                return obj.content_object.title
            case ModeratedObject.OBJECT_TYPE_POST_COMMENT:
                return obj.content_object.text
        return None

    @admin.action(description="Approve Moderation Object")
    def approve(self, request, queryset):
        for obj in queryset.all():
            request.user.approve_moderated_object(obj)

    @admin.action(description="Reject Moderation Object")
    def reject(self, request, queryset):
        for obj in queryset.all():
            request.user.reject_moderated_object(obj)

    @admin.action(description="Verify Moderation Object")
    def verify(self, request, queryset):
        for obj in queryset.all():
            request.user.verify_moderated_object(obj)

    @admin.action(description="Unverify Moderation Object")
    def unverify(self, request, queryset):
        for obj in queryset.all():
            request.user.unverify_moderated_object(obj)

    actions = [approve, reject, verify, unverify]


admin.site.register(ModeratedObject, ModeratedObjectAdmin)
