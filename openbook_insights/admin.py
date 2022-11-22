from django.contrib import admin

# Register your models here.
from openbook_insights.models import Insight


class InsightAdmin(admin.ModelAdmin):
    model = Insight
    search_fields = ("title", "description")
    date_hierarchy = "date_published"
    filter_horizontal = ("posts",)
    list_display = ("title", "description_preview", "creator")
    list_filter = ("creator",)

    @admin.display(description="Description Preview")
    def description_preview(self, obj):
        if (len(obj.description)) > 100:
            return obj.description[0:100] + "..."
        else:
            return obj.description


admin.site.register(Insight, InsightAdmin)
