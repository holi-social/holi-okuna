from django.contrib import admin
from .models import InspirationPostCategory, Topic, SDG, Skill, FeedPostCategory


@admin.register(InspirationPostCategory, Topic, SDG, Skill, FeedPostCategory)
class TermAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("title", "id")
    search_fields = ("title",)
