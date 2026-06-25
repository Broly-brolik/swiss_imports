from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=200)
    tin = models.CharField("No de transitaire/TIN/IDE", max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name