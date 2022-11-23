from django.contrib import admin

from openbook_spaces.models import Task


@admin.register(Task)
class SpaceTasksAdmin(admin.ModelAdmin):
    model = Task
    list_display = ("name", "location", "creator", "created")
