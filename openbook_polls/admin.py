from django.contrib import admin
from rangefilter.filters import DateRangeQuickSelectListFilterBuilder

from .models import Choice, Question


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0
    min_num = 2



class QuestionAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]
    list_display = [
        "id",
        "question_text",
        "created",
        "creator",
    ]
    list_filter = (
        ("created", DateRangeQuickSelectListFilterBuilder(title="Created")),
    )


admin.site.register(Question, QuestionAdmin)
