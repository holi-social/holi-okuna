from django.contrib import admin
from .models import InspirationPostCategory, Topic, SDG, Skill, FeedPostCategory


@admin.register(InspirationPostCategory, SDG, Skill, FeedPostCategory)
class TermAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("title", "id")
    search_fields = ("title",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("title", "id", "is_discover_spaces_default")
    search_fields = ("title",)
