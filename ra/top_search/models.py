from __future__ import unicode_literals
from django.db import models


class TopSearchBaseModel(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    slug = models.CharField(max_length=255)
    title = models.TextField()
    blob_text = models.TextField(null=True)
    identifier = models.CharField(max_length=255)

    class Meta:
        abstract = True
        managed = False
        db_table = 'ra_topsearch'


class TopSearchModel(TopSearchBaseModel):
    pass
