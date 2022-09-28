from django.contrib import admin

# Register your models here.
from openbook_insights.models import Insight


class InsightAdmin(admin.ModelAdmin):
    model = Insight
    search_fields = ('title',)
    #exclude = ['posts', 'post_comments']


admin.site.register(Insight, InsightAdmin)
