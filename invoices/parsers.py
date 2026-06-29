# invoices/parsers.py
import re
from decimal import Decimal, InvalidOperation

import pdfplumber

# Synonyms per canonical field, FR/EN/DE — extend this as you hit new supplier formats
HEADER_SYNONYMS = {
    "article_code": ["code", "référence", "ref", "art", "article", "sku"],
    "description": ["description", "désignation", "designation", "libellé", "bezeichnung", "produit"],
    "quantity": ["qté", "qte", "quantity", "quantité", "menge", "qty"],
    "unit_price": ["p.u. ht", "prix unitaire", "unit price", "p.u.", "preis", "pu ht"],
    "amount": ["montant ht", "montant", "amount", "total", "betrag"],
    "vat": ["tva", "vat", "mwst"],
}

NUMERIC_FIELDS = {"quantity", "unit_price", "amount", "vat"}


def _normalize_number(raw):
    """Handles European formatting: '1 234,56' -> 1234.56, '2,000' -> 2.000 (qty), etc."""
    if raw is None:
        return None
    s = str(raw).strip().replace("\xa0", "").replace(" ", "")
    if not s or s in ("-", "--"):
        return None
    s = s.replace(",", ".")
    # collapse any double decimal points from thousands-as-dot formats (e.g. "1.234.56")
    if s.count(".") > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _match_header(cell_text):
    """Returns the canonical field name a header cell most likely refers to, or None."""
    if not cell_text:
        return None
    text = cell_text.strip().lower()
    for field, synonyms in HEADER_SYNONYMS.items():
        if any(syn in text for syn in synonyms):
            return field
    return None


def _build_column_map(header_row):
    col_map = {}
    for idx, cell in enumerate(header_row):
        field = _match_header(cell)
        if field and field not in col_map:
            col_map[field] = idx
    return col_map


def _extract_tables_for_page(page):
    """Try line-based extraction first, fall back to whitespace-based."""
    tables = page.extract_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
    if tables and any(len(t) > 1 for t in tables):
        return tables
    return page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})


def _rows_from_tables(pdf_path, log):
    rows = []
    col_map = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = _extract_tables_for_page(page)
            if not tables:
                continue

            for table in tables:
                if not table:
                    continue
                start_row = 0
                # try to (re)detect header on this table
                candidate_map = _build_column_map(table[0])
                if len(candidate_map) >= 3:  # need at least code/description + one numeric to trust it
                    col_map = candidate_map
                    start_row = 1

                if not col_map:
                    log.append(f"Page {page_num}: no header detected yet, skipping table.")
                    continue

                for row in table[start_row:]:
                    if not row or all(c is None or str(c).strip() == "" for c in row):
                        continue
                    parsed = {}
                    for field, idx in col_map.items():
                        if idx >= len(row):
                            continue
                        val = row[idx]
                        parsed[field] = _normalize_number(val) if field in NUMERIC_FIELDS else (val or "").strip()

                    # skip section/recap rows: must have a real description and at least one numeric value
                    if not parsed.get("description") or not any(
                        parsed.get(f) for f in NUMERIC_FIELDS
                    ):
                        continue
                    rows.append(parsed)

    return rows


# Fallback: line-based regex for invoices with no extractable table structure at all.
# Pattern: CODE  DESCRIPTION....  QTY  PRICE  AMOUNT  [VAT]  (numbers use , or . as decimal)
LINE_PATTERN = re.compile(
    r"^(?P<article_code>[A-Z0-9][A-Z0-9._/-]{1,30})\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<quantity>[\d.,]+)\s+"
    r"(?P<unit_price>[\d.,]+)\s+"
    r"(?P<amount>[\d.,]+)\s*"
    r"(?P<vat>[\d.,]*)\s*$"
)


def _rows_from_regex(pdf_path, log):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for line in text.split("\n"):
                m = LINE_PATTERN.match(line.strip())
                if not m:
                    continue
                d = m.groupdict()
                rows.append({
                    "article_code": d["article_code"],
                    "description": d["description"].strip(),
                    "quantity": _normalize_number(d["quantity"]),
                    "unit_price": _normalize_number(d["unit_price"]),
                    "amount": _normalize_number(d["amount"]),
                    "vat": _normalize_number(d["vat"]) if d["vat"] else None,
                })
    if not rows:
        log.append("Regex fallback found no matching lines either.")
    return rows


def extract_invoice_lines(pdf_path):
    """
    Returns (rows, status, log) where:
      - rows: list of dicts with article_code, description, quantity, unit_price, amount, vat
      - status: 'success' | 'partial' | 'failed'
      - log: list of strings describing what happened, for parse_log
    """
    log = []
    rows = _rows_from_tables(pdf_path, log)

    if not rows:
        log.append("Table extraction found nothing usable — trying regex fallback.")
        rows = _rows_from_regex(pdf_path, log)

    if not rows:
        return [], "failed", log

    missing_code = sum(1 for r in rows if not r.get("article_code"))
    if missing_code:
        log.append(f"{missing_code}/{len(rows)} rows missing an article_code.")
        return rows, "partial", log

    return rows, "success", log