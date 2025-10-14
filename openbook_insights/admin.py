from django.contrib import admin
from django.forms import Select
from typing import get_args
from openbook_common.topics import TopicV2, topic_v2_slugs

from openbook_insights.models import Discussion, Initiative, Insight, Quote, Recommendation


class DiscussionInline(admin.TabularInline):
    model = Discussion
    extra = 0


class InsightRecommendationInline(admin.TabularInline):
    model = Recommendation
    readonly_fields = ["id"]
    exclude = ["link_preview"]
    extra = 0


class InsightQuoteInline(admin.StackedInline):
    model = Quote
    readonly_fields = ["id"]
    exclude = ["link_preview"]
    extra = 0
    min_num = 0
    max_num = 4


class InsightInitiativeInline(admin.TabularInline):
    model = Initiative
    readonly_fields = ["id"]
    exclude = ["link_preview"]
    extra = 0


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    model = Insight
    search_fields = ("title", "description")
    date_hierarchy = "date_published"
    filter_horizontal = ("posts", "polls")
    list_display = ("title", "description_preview", "creator", "header_image", "recommendations_count")

    inlines = [InsightRecommendationInline, InsightQuoteInline, InsightInitiativeInline, DiscussionInline]

    # Override the formfield_for_dbfield to customize the topic_v2 field widget
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "topic_v2":
            kwargs["widget"] = Select(
                choices=[("", "---------")] + list(zip(topic_v2_slugs, topic_v2_slugs, strict=True))
            )
            kwargs["required"] = False
        return super().formfield_for_dbfield(db_field, request, **kwargs)

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
