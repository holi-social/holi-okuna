from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from feed_posts.models import FeedPost, FeedConfig
from openbook_auth.models import UserRole


@admin.register(FeedPost)
class FeedPostAdminModel(admin.ModelAdmin):
    model = FeedPost

    list_display = (
        "id",
        "title",
        "description",
        "image",
        "visibility",
        "display_topics",
        "display_topics_v2",
        "language_code",
        "creator",
        "display_category",
        "display_is_co_founder",
        "priority_duration",
        "created_at",
    )

    list_filter = (("created_at", DateRangeQuickSelectListFilterBuilder()),)

    search_fields = ("title", "creator")

    def display_topics(self, obj):
        return ", ".join([topic.title for topic in obj.topics.all()])

    def display_topics_v2(self, obj):
        return ", ".join(obj.topics_v2)

    def display_category(self, obj):
        return obj.category.title if obj.category else ""

    def display_is_co_founder(self, obj):
        return obj.creator.role == UserRole.CO_FOUNDER

    display_topics.short_description = "Topics"
    display_topics_v2.short_description = "Topics V2"
    display_category.short_description = "Category"
    display_is_co_founder.short_description = "Co-founder's Post"


@admin.register(FeedConfig)
class FeedConfigAdmin(admin.ModelAdmin):
    list_display = ("priority_duration",)
    fieldsets = ((None, {"fields": ("priority_duration",)}),)
