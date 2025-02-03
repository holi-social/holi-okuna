from datetime import datetime

from django.db import models


# super simple model for a counter to simply insert a row with a counter name and timestamp
# to evaluate the counters value, a query needs to count the number of rows for the whole or a specific time frame
class Counter(models.Model):
    name: str = models.CharField(max_length=255)
    timestamp: datetime = models.DateTimeField(auto_now_add=True)
