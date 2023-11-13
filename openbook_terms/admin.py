from django.contrib import admin
from .models import InspirationPostCategory, Topic, SDG, Skill


@admin.register(InspirationPostCategory, Topic, SDG, Skill)
class TermAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("title", "id")
    search_fields = ("title",)
