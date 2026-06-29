from django.db import models
from customers.models import Customer
from catalog.models import SKU


class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="invoices")
    file = models.FileField(upload_to="invoices/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.original_filename or f"Invoice {self.pk}"


class InvoiceLine(models.Model):
    STATUS_CHOICES = [
        ("matched", "Matched — known SKU"),
        ("pending_review", "Pending review"),
        ("reviewed", "Reviewed and confirmed"),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    article_code = models.CharField(max_length=50)
    description_raw = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    matched_sku = models.ForeignKey(SKU, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoice_lines")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_review")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.article_code} ({self.invoice})"