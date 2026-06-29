from catalog.models import SKU


def match_known_skus(invoice):
    """
    For every InvoiceLine on this invoice, try to find an existing SKU
    for this customer + article_code. Updates matched_sku and status in place.
    Returns (matched_count, unmatched_lines).
    """
    customer = invoice.customer
    lines = invoice.lines.all()

    codes = [l.article_code for l in lines]
    known = {
        sku.article_code: sku
        for sku in SKU.objects.filter(customer=customer, article_code__in=codes)
    }

    matched_count = 0
    unmatched = []

    for line in lines:
        sku = known.get(line.article_code)
        if sku and sku.tariff_code_id:
            line.matched_sku = sku
            line.status = "matched"
            matched_count += 1
        else:
            line.status = "pending_review"
            unmatched.append(line)

    from invoices.models import InvoiceLine
    InvoiceLine.objects.bulk_update(lines, ["matched_sku", "status"])

    return matched_count, unmatched