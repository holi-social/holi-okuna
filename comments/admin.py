from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from .models import Comment


@admin.register(Comment)
class PostCommentAdmin(admin.ModelAdmin):
    model = Comment

    list_display = (
        "id",
        "text",
        "created",
        "commenter",
        "count_replies",
        "count_reactions",
        "count_mentions",
        "count_links",
        "is_deleted",
        "commentable",
    )
    list_filter = (("created", DateRangeQuickSelectListFilterBuilder(title="Created")),)
    search_fields = ("text", "commenter")
