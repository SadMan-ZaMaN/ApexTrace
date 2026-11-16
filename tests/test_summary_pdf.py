"""The one-page summary for faculty: docs/summary.html (generated, checked by test_docs) and its PDF.

The PDF is printed by experiments/33_summary_pdf.py with a browser, so it can't be rebuilt here.
These tests check what can be checked without one: the PDF has exactly one page, it was printed
from the CURRENT summary.html (the script records the HTML's SHA-256), and the public summary
contains no e-mail address. Reads only committed files; no F1 data is downloaded.
"""

import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_printer():
    spec = importlib.util.spec_from_file_location("summary_pdf", REPO_ROOT / "experiments" / "33_summary_pdf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_page_counter_worked_example():
    printer = load_printer()
    two_pages = b"<< /Type /Pages /Count 2 >> << /Type /Page >> << /Type/Page /Parent 1 0 R >>"
    assert printer.count_pdf_pages(two_pages) == 2          # the page tree (/Pages) is not a page
    assert printer.count_pdf_pages(b"<< /Type /Pages /Count 0 >>") == 0


def test_the_pdf_is_one_page_printed_from_the_current_summary():
    printer = load_printer()
    record = json.loads((REPO_ROOT / "results" / "33_summary_pdf" / "summary.json").read_text(encoding="utf-8"))
    pdf_bytes = (REPO_ROOT / "docs" / "summary.pdf").read_bytes()
    assert pdf_bytes.startswith(b"%PDF")
    assert printer.count_pdf_pages(pdf_bytes) == 1 == record["pages"]
    assert record["html_sha256"] == printer.html_sha256(REPO_ROOT / "docs" / "summary.html"), \
        "docs/summary.pdf was printed from an older summary: run experiments/33_summary_pdf.py"


def test_the_public_summary_has_no_email_address_and_no_unfilled_numbers():
    text = (REPO_ROOT / "docs" / "summary.html").read_text(encoding="utf-8")
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), "no e-mail address in the public summary"
    assert "{{" not in text and "}}" not in text
