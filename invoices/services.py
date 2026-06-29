# invoices/services.py
from django.utils import timezone
from .models import Invoice, InvoiceLine
from .parsers import extract_invoice_lines


def process_invoice(invoice: Invoice):
    rows, status, log = extract_invoice_lines(invoice.file.path)

    lines = [
        InvoiceLine(
            invoice=invoice,
            article_code=row.get("article_code") or "",
            description_raw=row.get("description") or "",
            quantity=row.get("quantity"),
            unit_price=row.get("unit_price"),
            status="pending_review",
        )
        for row in rows
    ]
    InvoiceLine.objects.bulk_create(lines)

    invoice.parse_status = status
    invoice.parse_log = "\n".join(log)
    invoice.processed_at = timezone.now()
    invoice.save(update_fields=["parse_status", "parse_log", "processed_at"])

    return status, len(lines)