from django.db import models
from pgvector.django import VectorField

class TariffCode(models.Model):
    code = models.CharField(max_length=12, unique=True)
    text_fr = models.TextField()              # was CharField(max_length=500)
    text_de = models.TextField(blank=True)     # was CharField(max_length=500, blank=True)
    breadcrumb_fr = models.TextField(blank=True)
    embedding = VectorField(dimensions=1024, null=True, blank=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.code} — {self.text_fr}"