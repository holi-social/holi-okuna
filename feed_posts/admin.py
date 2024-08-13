from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from feed_posts.models import FeedPost
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
        "language_code",
        "creator",
        "display_category",
        "display_is_founder",
        "priority_duration",
        "created_at",
    )

    list_filter = (("created_at", DateRangeQuickSelectListFilterBuilder()),)

    search_fields = ("title", "creator")

    def display_topics(self, obj):
        return ", ".join([topic.title for topic in obj.topics.all()])

    def display_category(self, obj):
        return obj.category.title

    def display_is_founder(self, obj):
        return obj.creator.role == UserRole.FOUNDER

    display_topics.short_description = "Topics"
    display_category.short_description = "Category"
    display_is_founder.short_description = "Founder's Post"
