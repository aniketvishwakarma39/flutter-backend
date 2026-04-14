
from django.db import models

class UserLocation(models.Model):
    name = models.CharField(max_length=100)
    token = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.name