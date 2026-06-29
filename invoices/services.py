# invoices/services.py
from django.utils import timezone
from .models import Invoice, InvoiceLine
from .parsers import extract_invoice_lines
from classification.services.matcher import match_known_skus



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

    from .parsers import detect_invoice_numbers
    invoice_numbers = detect_invoice_numbers(invoice.file.path)
    if len(invoice_numbers) > 1:
        log.append(f"WARNING: multiple invoice numbers detected in one file: {invoice_numbers}")
    
    InvoiceLine.objects.bulk_create(lines)
    matched_count, unmatched_lines = match_known_skus(invoice)

    invoice.parse_status = status
    invoice.parse_log = "\n".join(log)
    invoice.processed_at = timezone.now()
    invoice.save(update_fields=["parse_status", "parse_log", "processed_at"])

    return status, len(lines)