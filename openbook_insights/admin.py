from django.contrib import admin

from openbook_insights.models import Insight, Recommendation, Quote


class InsightRecommendationInline(admin.TabularInline):
    model = Recommendation
    readonly_fields = ["id"]
    exclude = ["link_preview"]
    extra = 1


class InsightQuoteInline(admin.StackedInline):
    model = Quote
    readonly_fields = ["id"]
    exclude = ["link_preview"]
    extra = 0
    min_num = 2
    max_num = 4


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    model = Insight
    search_fields = ("title", "description")
    date_hierarchy = "date_published"
    filter_horizontal = ("posts",)
    list_display = ("title", "description_preview", "creator", "header_image", "recommendations_count")
    # This filter makes the admin UI slow when there is a lot of users
    # list_filter = ("creator",)

    inlines = [InsightRecommendationInline, InsightQuoteInline]

    @admin.display(description="Description Preview")
    def description_preview(self, obj):
        if (len(obj.description)) > 100:
            return obj.description[0:100] + "..."
        else:
            return obj.description

    @admin.display(description="Number of recommendations")
    def recommendations_count(self, obj: Insight) -> str:
        recommendations_count = obj.recommendations.count()
        if recommendations_count == 1:
            return "1 recommendation"

        return f"{recommendations_count} recommendations"
