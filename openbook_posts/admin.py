from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from comments.models import Comment
from openbook_circles.models import Circle
from openbook_posts.models import Post, PostImage, PostReaction


class PostImageInline(admin.TabularInline):
    model = PostImage

    def has_delete_permission(self, request, obj=None):
        return False


class PostCommentInline(GenericTabularInline):
    model = Comment
    ct_field = "commentable_type"
    ct_fk_field = "commentable_id"

    readonly_fields = ("commenter", "text", "created")

    def has_add_permission(self, request, obj):
        return False


class PostReactionInline(admin.TabularInline):
    model = PostReaction

    readonly_fields = ["reactor"]

    def has_add_permission(self, request, obj):
        return False


class PostCircleInline(admin.TabularInline):
    model = Circle.posts.through

    def has_delete_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request, obj):
        return True


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostReactionInline, PostImageInline, PostCommentInline]
    exclude = ["links"]

    list_display = (
        "id",
        "title",
        "created",
        "creator",
        "is_public",
        "status",
        "is_deleted",
        "count_comments",
        "count_reactions",
        "has_text",
        "has_image",
    )
    list_filter = (
        "is_public",
        "status",
        ("created", DateRangeQuickSelectListFilterBuilder(title="Created")),
    )
    search_fields = ("title", "text")

    def has_add_permission(self, request, obj=None):
        return True  # needs to be true for creating posts via /admin

    def has_change_permission(self, request, obj=None):
        return True  # needs to be true for editing posts via /admin

    def save_model(self, request, obj, form, change):
        if change:
            old_post = Post.objects.get(id=obj.id)
            is_publication = old_post.status != Post.STATUS_PUBLISHED and obj.status == Post.STATUS_PUBLISHED
        else:
            is_publication = obj.status == Post.STATUS_PUBLISHED

        super().save_model(request, obj, form, change)
        if is_publication:
            obj._publish()
