from django.contrib import admin
from .models import SDG, FeedPostCategory


@admin.register(SDG, FeedPostCategory)
class TermAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    list_display = ("title", "id")
    search_fields = ("title",)
