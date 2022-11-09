from django.contrib import admin
from .models import Topic, SDG, Skill


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "id")
    search_fields = ("title",)


@admin.register(SDG)
class SDGAdmin(admin.ModelAdmin):
    list_display = ("title", "id")
    search_fields = ("title",)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("title", "id")
    search_fields = ("title",)
