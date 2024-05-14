from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin

from openbook_moderation.models import (
    ModerationCategory,
    ModerationReport,
    ModeratedObject,
)


def linkify(field_name):
    """
    Converts a foreign key value into clickable links.

    If field_name is 'parent', link text will be str(obj.parent)
    Link will be admin url for the admin url for obj.parent.id:change
    """

    def _linkify(obj):
        try:
            linked_obj = getattr(obj, field_name)
        except:  # noqa: E722
            return "-"

        if linked_obj is None:
            return "-"

        app_label = linked_obj._meta.app_label
        model_name = linked_obj._meta.model_name
        view_name = f"admin:{app_label}_{model_name}_change"
        link_url = reverse(view_name, args=[linked_obj.pk])
        return format_html('<a href="{}">{}</a>', link_url, linked_obj)

    _linkify.short_description = field_name  # Sets column name
    return _linkify


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

    change_form_template = "moderation_changeform.html"
    list_display = ("id", "object_type", linkify(field_name="content_object"), "object_repr", "status", "verified")
    readonly_fields = [
        "verified",
        "category",
        "description",
        "community",
        "status",
        "object_type",
        "object_id",
        "content_type",
        linkify(field_name="content_object"),
        "object_full_repr",
    ]

    def response_change(self, request, obj):
        if "_approve" in request.POST:
            request.user.approve_moderated_object(obj)
            self.message_user(request, "Approved")
            return HttpResponseRedirect(".")
        if "_reject" in request.POST:
            request.user.reject_moderated_object(obj)
            self.message_user(request, "Rejected")
            return HttpResponseRedirect(".")
        if "_verify" in request.POST:
            request.user.verify_moderated_object(obj)
            self.message_user(request, "Verified")
            return HttpResponseRedirect(".")
        if "_unverify" in request.POST:
            request.user.unverify_moderated_object(obj)
            self.message_user(request, "Unverified")
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    @admin.display(description="Content")
    def object_repr(self, obj):
        return self.object_to_text(obj, 100)

    @admin.display(description="Content")
    def object_full_repr(self, obj):
        return self.object_to_text(obj)

    def object_to_text(self, obj, length=None):
        if obj is None or obj.content_object is None:
            return "ERROR: Content was deleted"
        match obj.object_type:
            case ModeratedObject.OBJECT_TYPE_POST:
                return (
                    str(obj.content_object.id) + " / " + obj.content_object.title + " / " + obj.content_object.text
                )[:length]
            case ModeratedObject.OBJECT_TYPE_POST_COMMENT:
                return (str(obj.content_object.id) + " / " + obj.content_object.text)[:length]
            case ModeratedObject.OBJECT_TYPE_USER:
                return (
                    obj.content_object.username
                    + " / "
                    + str(obj.content_object.id)
                    + " / "
                    + obj.content_object.email
                    + " / "
                    + obj.content_object.profile.full_name()
                )[:length]
            case ModeratedObject.OBJECT_TYPE_COMMUNITY:
                return (str(obj.content_object.id) + " / " + obj.content_object.title)[:length]
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
