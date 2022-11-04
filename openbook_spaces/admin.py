from django.contrib import admin

# Register your models here.
from openbook_spaces.models import Space, SpaceMember

class SpaceAdmin(admin.ModelAdmin):
    model = Space

class SpaceMemberAdmin(admin.ModelAdmin):
    model = SpaceMember

admin.site.register(Space, SpaceAdmin)
admin.site.register(SpaceMember, SpaceMemberAdmin)
