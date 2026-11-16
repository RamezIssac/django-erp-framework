from django.db import models


class SecretDocument(models.Model):
    """Exists so tests can gate pages on a real permission."""

    name = models.CharField(max_length=50)
