from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.html import format_html
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
        "link_to_commentable",
        "language_code",
        "count_replies",
        "count_reactions",
        "count_mentions",
        "count_links",
        "is_deleted",
    )
    list_filter = (("created", DateRangeQuickSelectListFilterBuilder(title="Created")),)
    search_fields = ("text", "commenter")
    ordering = ("-created",)

    def link_to_commentable(self, obj):
        content_type = ContentType.objects.get_for_model(model=obj.commentable_type.model_class())
        link = reverse("admin:%s_%s_change" % (content_type.app_label, content_type.model), args=(obj.commentable_id,))
        commentable = obj.get_commentable(obj.commentable_id, obj.commentable_type)
        return format_html(
            '<a href="{}">{}</a>',
            link,
            commentable,
        )

    link_to_commentable.short_description = "Commentable"  # new
