from django.contrib import admin

from openbook_insights.models import Insight


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    model = Insight
    search_fields = ("title", "description")
    date_hierarchy = "date_published"
    filter_horizontal = ("posts",)
    list_display = ("title", "description_preview", "creator", "header_image", "header_image_blurhash")
    # This filter makes the admin UI slow when there is a lot of users
    # list_filter = ("creator",)

    @admin.display(description="Description Preview")
    def description_preview(self, obj):
        if (len(obj.description)) > 100:
            return obj.description[0:100] + "..."
        else:
            return obj.description
