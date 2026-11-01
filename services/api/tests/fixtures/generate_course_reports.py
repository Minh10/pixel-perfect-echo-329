"""Distinct synthetic annual reports for the short-course trend demonstration.

Both issuers are fictional. The figures are defined here and are not copied from a real filing.
Run: python tests/fixtures/generate_course_reports.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle

OUT = Path(__file__).parent
W, H = A4


def _report(path: Path, year: int, prior: int, revenue: tuple[str, str], profit: tuple[str, str]) -> None:
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    c.setTitle(f"Fictional Example Holdings plc — Annual Report {year} (synthetic test fixture)")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, H - 90, "Fictional Example Holdings plc")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, H - 114, f"Annual Report {year}")
    c.setFont("Helvetica", 11)
    c.drawString(72, H - 146, "SYNTHETIC TEST FIXTURE. This is not a real company and contains no real financial data.")
    c.drawString(72, H - 162, f"Year ended 31 December {year}. All figures are presented in GBP millions.")
    rows = [
        ["", str(year), str(prior)],
        ["Revenue", revenue[0], revenue[1]],
        ["Operating profit", profit[0], profit[1]],
    ]
    table = Table(rows, colWidths=[180, 90, 90], rowHeights=22)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    _, height = table.wrapOn(c, W, H)
    top = H - 210
    table.drawOn(c, 72, top - height)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(72, top - height - 16, f"Table 1: Summary income statement (GBP millions), synthetic, year {year}")
    c.showPage()
    c.save()


def main() -> None:
    _report(OUT / "synthetic_ar_2024.pdf", 2024, 2023, ("3,200", "2,900"), ("410", "360"))
    _report(OUT / "synthetic_ar_2025.pdf", 2025, 2024, ("3,550", "3,200"), ("470", "410"))
    print("wrote", OUT / "synthetic_ar_2024.pdf")
    print("wrote", OUT / "synthetic_ar_2025.pdf")


if __name__ == "__main__":
    main()
