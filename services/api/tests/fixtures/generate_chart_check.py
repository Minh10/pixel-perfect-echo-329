"""Synthetic chart-versus-table fixture.

The chart prints North 240, South 158, East 90, and West 21.
The table reports the same figures except East, which is 150.
Both pages say this is a synthetic test fixture and not a real company.

Run: python tests/fixtures/generate_chart_check.py
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

OUT = Path(__file__).parent
W, H = A4
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


def chart_png() -> bytes:
    img = Image.new("RGB", (1100, 640), "white")
    draw = ImageDraw.Draw(img)
    title = ImageFont.truetype(str(FONT_BOLD), 36)
    label = ImageFont.truetype(str(FONT), 32)
    value = ImageFont.truetype(str(FONT_BOLD), 40)
    draw.text((40, 24), "Segment revenue 2025", fill="black", font=title)
    draw.text((40, 72), "GBP millions", fill="black", font=label)
    bars = [("North", 240), ("South", 158), ("East", 90), ("West", 21)]
    for index, (name, amount) in enumerate(bars):
        left = 120 + index * 240
        top = 560 - int(amount * 1.6)
        draw.rectangle([left, top, left + 140, 560], fill=(30, 64, 140))
        amount_text = str(amount)
        box = draw.textbbox((0, 0), amount_text, font=value)
        draw.text((left + 70 - (box[2] - box[0]) / 2, top - 52), amount_text, fill="black", font=value)
        box = draw.textbbox((0, 0), name, font=label)
        draw.text((left + 70 - (box[2] - box[0]) / 2, 575), name, fill="black", font=label)
    draw.line([70, 560, 1040, 560], fill="black", width=3)
    draw.line([70, 140, 70, 560], fill="black", width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def main() -> None:
    path = OUT / "synthetic_chart_check.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    pdf.setTitle("Fictional Example Holdings plc — segment chart check 2025 (synthetic test fixture)")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(72, H - 80, "Fictional Example Holdings plc")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(72, H - 110, "SYNTHETIC TEST FIXTURE. This is not a real company and contains no real financial data.")
    pdf.drawString(72, H - 128, "Segment revenue for the year ended 31 December 2025. Figures are in GBP millions.")
    rows = [
        ["", "2025"],
        ["North", "240"],
        ["South", "158"],
        ["East", "150"],
        ["West", "21"],
    ]
    table = Table(rows, colWidths=[180, 90], rowHeights=22)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    _, height = table.wrapOn(pdf, W, H)
    top = H - 170
    table.drawOn(pdf, 72, top - height)
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(72, top - height - 16, "Table 1: Segment revenue (GBP millions), synthetic, 2025")
    pdf.showPage()
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(72, H - 80, "Segment performance")
    image = chart_png()
    pdf.drawImage(ImageReader(io.BytesIO(image)), 72, H - 460, 450, 262)
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(72, H - 480, "Figure 1: Segment revenue, 2025 (synthetic test fixture)")
    pdf.showPage()
    pdf.save()
    print("wrote", path)


if __name__ == "__main__":
    main()
