from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

# Register your models here.
from openbook_common.models import Emoji, EmojiGroup, Badge, ProxyBlacklistedDomain, AppVersion


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


@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    readonly_fields = ("created",)
    list_display = ("version", "need_update", "app_store_url", "play_store_url", "created")
