from django.db import models

# Create your models here.
from openbook.settings import INSIGHT_TITLE_MAX_LENGTH, INSIGHT_HEADER_IMAGE_URL_MAX_LENGTH
from openbook_auth.models import User

class Insight(models.Model):
    title = models.CharField(max_length=INSIGHT_TITLE_MAX_LENGTH, blank=False)
    description = models.TextField(blank=False)
    curator = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='curated_insights', blank=True, null=True)
    date_published = models.DateField(blank=False)
    header_image = models.CharField(max_length=INSIGHT_HEADER_IMAGE_URL_MAX_LENGTH, blank=True, null=True)

#    class Meta:
#        verbose_name_plural = 'insights'