import time
from datetime import date

import openpyxl
from openai import OpenAI
from django.core.management.base import BaseCommand
from tariff.models import TariffCode
from dotenv import load_dotenv
import os

load_dotenv()

EMBEDDING_MODEL = "baai/bge-m3"
BATCH_SIZE = 100

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)


class Command(BaseCommand):
    help = "Import the Swiss Tares tariff structure xlsx into TariffCode, with embeddings."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str)
        parser.add_argument("--valid-from", type=str, default=None,
                             help="YYYY-MM-DD, defaults to today")
        parser.add_argument("--skip-embeddings", action="store_true",
                             help="Load text only, skip embedding API calls (faster for testing)")

    def handle(self, *args, **options):
        path = options["xlsx_path"]
        valid_from = (
            date.fromisoformat(options["valid_from"])
            if options["valid_from"] else date.today()
        )
        skip_embeddings = options["skip_embeddings"]

        self.stdout.write(f"Reading {path} ...")
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(min_row=2, values_only=True))

        # hierarchy TAB/TN2 = chapter, TN4 = heading,
        # VT6/VT8/TN6/TN8 = nested levels. Only TN6/TN8 rows carry a real tariff code.
        stack = {}
        leaves = []  # (code, text_fr, text_de, breadcrumb_fr)

        for r in rows:
            typ, numm, indent = r[0], r[1], r[2]
            text_d, text_f = r[4], r[5]

            if typ in ("TAB", "TN2"):
                stack = {}
            elif typ == "TN4":
                stack = {}
            elif typ in ("VT6", "VT8", "TN6", "TN8"):
                ind = indent if indent is not None else max(stack.keys(), default=0) + 1
                stack[ind] = text_f
                for k in [k for k in stack if k > ind]:
                    del stack[k]
                if typ in ("TN6", "TN8") and numm:
                    breadcrumb = " / ".join(stack[k] for k in sorted(stack.keys()))
                    leaves.append((str(numm), text_f or "", text_d or "", breadcrumb))

        self.stdout.write(f"Found {len(leaves)} leaf tariff codes.")

        existing = {tc.code: tc for tc in TariffCode.objects.all()}
        to_create, to_update = [], []

        for code, text_fr, text_de, breadcrumb in leaves:
            obj = existing.get(code)
            if obj:
                obj.text_fr = text_fr
                obj.text_de = text_de
                obj.breadcrumb_fr = breadcrumb
                to_update.append(obj)
            else:
                to_create.append(TariffCode(
                    code=code, text_fr=text_fr, text_de=text_de,
                    breadcrumb_fr=breadcrumb, valid_from=valid_from,
                ))

        if to_create:
            TariffCode.objects.bulk_create(to_create, batch_size=500)
            self.stdout.write(f"Created {len(to_create)} new codes.")
        if to_update:
            TariffCode.objects.bulk_update(
                to_update, ["text_fr", "text_de", "breadcrumb_fr"], batch_size=500
            )
            self.stdout.write(f"Updated {len(to_update)} existing codes.")

        if skip_embeddings:
            self.stdout.write(self.style.WARNING("Skipped embeddings (--skip-embeddings)."))
            return

        pending = list(TariffCode.objects.filter(embedding__isnull=True))
        self.stdout.write(f"Embedding {len(pending)} codes via {EMBEDDING_MODEL} ...")

        for i in range(0, len(pending), BATCH_SIZE):
            batch = pending[i:i + BATCH_SIZE]
            texts = [f"{tc.breadcrumb_fr} / {tc.text_fr}".strip(" /") for tc in batch]
            result = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            for tc, item in zip(batch, result.data):
                tc.embedding = item.embedding
            TariffCode.objects.bulk_update(batch, ["embedding"])
            self.stdout.write(f"  embedded {min(i + BATCH_SIZE, len(pending))}/{len(pending)}")
            time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS("Done."))