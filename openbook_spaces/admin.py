from django.contrib import admin

# Register your models here.
from openbook_spaces.models import Space

class SpaceAdmin(admin.ModelAdmin):
    model = Space

admin.site.register(Space, SpaceAdmin)
