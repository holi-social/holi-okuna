from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from feed_posts.models import FeedPost


@admin.register(FeedPost)
class FeedPostAdminModel(admin.ModelAdmin):
    model = FeedPost

    list_display = (
        "id",
        "title",
        "description",
        "image",
        "visibility",
        "category",
        "display_topics",
        "language_code",
        "creator",
        "created_at",
    )

    list_filter = (("created_at", DateRangeQuickSelectListFilterBuilder()),)

    search_fields = ("title", "creator")

    def display_topics(self, obj):
        return ", ".join([topic.title for topic in obj.topics.all()])

    display_topics.short_description = "Topics"
