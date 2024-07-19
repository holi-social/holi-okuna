from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from feed_posts.models import FeedPost
from openbook_common.types import LanguageCode


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
        "display_language",
        "creator",
        "created_at",
    )

    list_filter = (("created_at", DateRangeQuickSelectListFilterBuilder()),)

    search_fields = ("title", "creator")

    def display_topics(self, obj):
        return ", ".join([topic.title for topic in obj.topics.all()])

    def display_language(self, obj):
        return LanguageCode(obj.language_code).label

    display_topics.short_description = "Topics"
    display_language.short_description = "Language"
