from django.db import models
from customers.models import Customer
from tariff.models import TariffCode


class SKU(models.Model):
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("llm", "LLM-suggested, confirmed"),
        ("auto", "Auto-accepted, high confidence"),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="skus")
    article_code = models.CharField(max_length=50)
    description = models.CharField(max_length=300, blank=True)
    tariff_code = models.ForeignKey(TariffCode, null=True, on_delete=models.PROTECT, related_name="skus")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="manual")
    confidence = models.FloatField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("customer", "article_code")
        indexes = [
            models.Index(fields=["customer", "article_code"]),
        ]

    def __str__(self):
        return f"{self.customer} / {self.article_code} → {self.tariff_code or 'unclassified'}"


class ClassificationHistory(models.Model):
    """Append-only audit trail — every correction ever made to a SKU's tariff code.
    Required for customs defensibility: if a code is corrected later, you need to know
    what code was actually used on the original declaration."""
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name="history")
    tariff_code = models.ForeignKey(TariffCode, on_delete=models.PROTECT)
    changed_by = models.ForeignKey("auth.User", null=True, on_delete=models.SET_NULL)
    changed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.sku.article_code} → {self.tariff_code.code} ({self.changed_at:%Y-%m-%d})"