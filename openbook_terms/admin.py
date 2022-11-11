from django.contrib import admin
from .models import Topic, SDG, Skill


@admin.register(Topic, SDG, Skill)
class TermAdmin(admin.ModelAdmin):
    list_display = ("title", "id")
    search_fields = ("title",)
