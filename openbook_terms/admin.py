from django.contrib import admin
from .models import Topic, SDG, Skill


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "id")


@admin.register(SDG)
class SDGAdmin(admin.ModelAdmin):
    list_display = ("title", "id")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("title", "id")
