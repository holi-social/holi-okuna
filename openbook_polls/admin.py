from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from .models import Choice, Poll


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    min_num = 2

    readonly_fields = ["votes"]


class PollAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]
    list_display = [
        "id",
        "question_text",
        "created",
        "creator",
    ]
    list_filter = (("created", DateRangeQuickSelectListFilterBuilder(title="Created")),)


admin.site.register(Poll, PollAdmin)
