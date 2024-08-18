from django.contrib import admin
from django.contrib.postgres.fields import ArrayField
from django.db.models import F, Func, IntegerField, Value
from modeltranslation.admin import TranslationAdmin

from openbook_common.enums import NeedUpdateType
from openbook_common.forms import AppVersionForm
from openbook_common.models import Emoji, EmojiGroup, Badge, ProxyBlacklistedDomain, AppVersion, FeatureToggle


class EmojiGroupEmoji(admin.TabularInline):
    model = Emoji


@admin.register(EmojiGroup)
class EmojiGroupAdmin(TranslationAdmin):
    inlines = [EmojiGroupEmoji]

    list_display = ("id", "keyword", "created", "color", "order")


@admin.register(Emoji)
class EmojiAdmin(TranslationAdmin):
    pass


@admin.register(Badge)
class BadgeAdmin(TranslationAdmin):
    pass


@admin.register(ProxyBlacklistedDomain)
class ProxyBlacklistDomainAdmin(admin.ModelAdmin):
    list_display = ("domain",)


@admin.action(description="Mark selected app versions as mandatory update")
def make_mandatory(modeladmin, request, queryset):
    queryset.update(need_update=NeedUpdateType.MANDATORY)


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    form = AppVersionForm
    readonly_fields = (
        "semantic_version",
        "created",
    )
    list_display = (
        "semantic_version",
        "build_number",
        "need_update",
        "app_store_url",
        "play_store_url",
        "created",
    )
    search_fields = ("version", "build_number")
    actions = [make_mandatory]

    # create a readonly, nicely sortable semantic version field for displaying it in the list and sorting by.
    # For this, we internally use an integer array. created from the version field.
    def get_queryset(self, request):
        qs = super(AppVersionAdmin, self).get_queryset(request)
        qs = qs.annotate(
            sv=Func(
                F("version"),
                Value("."),
                function="string_to_array",
                template="%(function)s(%(expressions)s)::int[]",
                output_field=ArrayField(IntegerField()),
            )
        )
        return qs

    # pretty display the sortable semantic version field as string
    def semantic_version(self, obj):
        return ".".join(str(x) for x in obj.sv)

    # use the underlying derived, readonly field for sorting semvers
    semantic_version.admin_order_field = "sv"

    # hide the readonly fields in creation and edit forms
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing
            return self.readonly_fields
        return ()  # Creating


@admin.register(FeatureToggle)
class FeatureToggleAdmin(admin.ModelAdmin):
    readonly_fields = ("created",)
    list_display = ("name", "status", "created")
    ordering = ("name",)
