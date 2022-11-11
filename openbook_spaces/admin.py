from django.contrib import admin

# Register your models here.
from openbook_spaces.models import Space, SpaceMember
from openbook_spaces.models import Task


class SpaceAdmin(admin.ModelAdmin):
    model = Space
    list_display = ("title", "creator", "created")


class SpaceTasksAdmin(admin.ModelAdmin):
    model = Task
    list_display = ("name", "location", "creator", "created")


class SpaceMemberAdmin(admin.ModelAdmin):
    model = SpaceMember


admin.site.register(Space, SpaceAdmin)
admin.site.register(Task, SpaceTasksAdmin)
admin.site.register(SpaceMember, SpaceMemberAdmin)
