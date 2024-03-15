from django.contrib import admin

from .models import Choice, Question


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 3


class QuestionAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {"fields": ["question_text"]}),
        ("Date information", {"fields": ["pub_date"], "classes": ["show"]}),
        (None, {"fields": ["creator"]}),
    ]

    inlines = [ChoiceInline]
    list_display = [
        "id",
        "question_text",
        "pub_date",
        "creator",
    ]


admin.site.register(Question, QuestionAdmin)
