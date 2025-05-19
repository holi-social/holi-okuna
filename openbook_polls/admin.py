from django.contrib import admin
from django.core.exceptions import ValidationError
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from .models import Choice, Poll


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    min_num = 2

    readonly_fields = ["votes"]


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        poll = form.instance
        if poll.max_choices and poll.choices.exists():
            if poll.max_choices > poll.choices.count():
                raise ValidationError(
                    "The maximum number of choices must be less than or equal to the number of choices."
                )

    list_display = [
        "id",
        "question_text",
        "is_multi_select",
        "max_choices",
        "created",
        "creator",
    ]
    list_filter = (("created", DateRangeQuickSelectListFilterBuilder(title="Created")),)
