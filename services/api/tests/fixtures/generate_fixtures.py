"""Generate representative financial PDF fixtures with known ground-truth layout.

All content is SYNTHETIC and refers to a fictional issuer.  Nothing here is real financial data.
The point is that we know exactly where every element was drawn, so tests can check that the
parsers report correct page numbers and bounding boxes (provenance), not just text.

Usage:  python tests/fixtures/generate_fixtures.py   (writes PDFs + *.layout.json next to this file)
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

OUT = Path(__file__).parent
W, H = A4  # 595.27 x 841.89 pt
ISSUER = "Fictional Example Holdings plc (synthetic test fixture)"


def tl(x: float, y_top_bl: float, w: float, h: float) -> list[float]:
    """reportlab (bottom-left) box with top edge at y_top_bl -> [l, t, r, b] top-left origin."""
    return [round(x, 2), round(H - y_top_bl, 2), round(x + w, 2), round(H - y_top_bl + h, 2)]


def bar_chart_png() -> bytes:
    img = Image.new("RGB", (800, 480), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=22)
    d.text((40, 15), "Revenue by segment (GBP m) - synthetic", fill="black", font=font)
    bars = [("North", 240), ("South", 158), ("East", 61), ("West", 21)]
    for i, (label, v) in enumerate(bars):
        x0 = 80 + i * 170
        d.rectangle([x0, 420 - v * 1.3, x0 + 110, 420], fill=(40, 70, 140))
        d.text((x0 + 10, 430), label, fill="black", font=font)
    d.line([60, 420, 760, 420], fill="black", width=2)
    d.line([60, 60, 60, 420], fill="black", width=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def annual_report_excerpt() -> dict:
    path = OUT / "annual_report_excerpt.pdf"
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle("Fictional Example Holdings - Annual Report 2025 (synthetic fixture)")
    layout: dict = {"file": path.name, "pageSize": [W, H], "pages": {}}

    # ---- page 1: cover
    c.setFont("Helvetica-Bold", 24)
    c.drawString(72, H - 140, "Fictional Example Holdings plc")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, H - 170, "Annual Report and Accounts 2025")
    c.setFont("Helvetica", 11)
    c.drawString(72, H - 210, "This synthetic document covers the financial year ended 31 December 2025.")
    c.drawString(72, H - 226, "It exists only to test document parsing and contains no real data.")
    layout["pages"]["1"] = {"title": "Fictional Example Holdings plc"}
    c.showPage()

    # ---- page 2: financial review with ruled income statement table
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, H - 90, "Financial review")
    c.setFont("Helvetica", 11)
    c.drawString(72, H - 120, "Group revenue increased 12.4% to GBP 4,812 million in 2025, while operating")
    c.drawString(72, H - 135, "profit rose to GBP 703 million. All figures are presented in GBP millions.")
    rows = [
        ["", "2025", "2024", "Change"],
        ["Revenue", "4,812", "4,281", "+12.4%"],
        ["Cost of sales", "(3,018)", "(2,722)", "+10.9%"],
        ["Gross profit", "1,794", "1,559", "+15.1%"],
        ["Operating expenses", "(1,091)", "(968)", "+12.7%"],
        ["Operating profit", "703", "591", "+18.9%"],
        ["Profit for the year", "471", "392", "+20.2%"],
    ]
    t = Table(rows, colWidths=[180, 90, 90, 90], rowHeights=22)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    tw, th = t.wrapOn(c, W, H)
    table_top = H - 170
    t.drawOn(c, 72, table_top - th)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(72, table_top - th - 16, "Table 1: Summary income statement (GBP m), synthetic data")
    layout["pages"]["2"] = {
        "heading": {"text": "Financial review", "bbox": tl(72, H - 90 + 14, 140, 18)},
        "table": {"bbox": tl(72, table_top, tw, th), "rows": rows},
    }
    c.showPage()

    # ---- page 3: segment chart (raster image) + caption + narrative
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, H - 90, "Segment performance")
    img_w, img_h = 400, 240
    img_top = H - 120
    c.drawImage(ImageReader(io.BytesIO(bar_chart_png())), 72, img_top - img_h, img_w, img_h)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(72, img_top - img_h - 16, "Figure 1: Revenue by segment, 2025 (synthetic)")
    c.setFont("Helvetica", 11)
    c.drawString(72, img_top - img_h - 50, "North remained the largest segment, contributing 50% of Group revenue.")
    layout["pages"]["3"] = {"figure": {"bbox": tl(72, img_top, img_w, img_h)}}
    c.showPage()
    c.save()
    return layout


def scanned_page() -> dict:
    """One page that is only a raster image of text: no text layer (OCR would be required)."""
    path = OUT / "scanned_statement.pdf"
    img = Image.new("RGB", (1240, 1754), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=36)
    d.text((120, 160), "Balance sheet (scanned, synthetic)", fill="black", font=font)
    d.text((120, 260), "Total assets      9,999", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.drawImage(ImageReader(io.BytesIO(buf.getvalue())), 0, 0, W, H)
    c.showPage()
    c.save()
    return {"file": path.name, "pages": {"1": {"hasTextLayer": False}}}


def encrypted() -> dict:
    path = OUT / "encrypted.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Confidential synthetic fixture")
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    return {"file": path.name}


def corrupt() -> dict:
    # Truncated real PDF: header present, body/xref cut off -> cannot be opened at all.
    src = (OUT / "annual_report_excerpt.pdf").read_bytes()
    (OUT / "truncated.pdf").write_bytes(src[:600])
    # Header + garbage: MuPDF's repair mode opens it but finds no page tree.
    path = OUT / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.7\n1 0 obj << /Type /Catalog >> garbage without xref or pages\n")
    return {"file": path.name}


def main() -> None:
    layouts = [annual_report_excerpt(), scanned_page(), encrypted(), corrupt()]
    for lay in layouts:
        if "pages" in lay:
            (OUT / (Path(lay["file"]).stem + ".layout.json")).write_text(json.dumps(lay, indent=2))
    (OUT / "not_a_pdf.txt").write_text("This is plain text, not a PDF.\n")
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
