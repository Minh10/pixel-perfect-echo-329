"""Overlay ground truth, true positives, false positives and false negatives on a page image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

COLORS = {"gt": (0, 160, 0), "tp": (0, 90, 255), "fp": (230, 0, 0), "fn": (255, 140, 0)}
LEGEND = [("ground truth", "gt"), ("TP prediction", "tp"), ("FP prediction", "fp"), ("FN (missed GT)", "fn")]


def _dashed(d: ImageDraw.ImageDraw, box, color, width=3, dash=10):
    x0, y0, x1, y1 = box
    for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        length = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        n = max(1, int(length // dash))
        for k in range(0, n, 2):
            s, e = k / n, min(1, (k + 1) / n)
            d.line([(a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s),
                    (a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e)], fill=color, width=width)


def draw(image: Image.Image, items: list[dict], out: Path, title: str) -> None:
    """items: {kind: gt|tp|fp|fn, box: (x0,y0,x1,y1), label: str, score: float|None}"""
    img = image.convert("RGB").copy()
    d = ImageDraw.Draw(img)
    for it in sorted(items, key=lambda i: ["gt", "fn", "fp", "tp"].index(i["kind"])):
        c = COLORS[it["kind"]]
        if it["kind"] == "fn":
            _dashed(d, it["box"], c, width=4)
        else:
            d.rectangle(it["box"], outline=c, width=2 if it["kind"] == "gt" else 3)
        tag = it["label"] + (f" {it['score']:.2f}" if it.get("score") is not None else "")
        d.text((it["box"][0] + 3, it["box"][1] + 2), tag, fill=c)
    d.rectangle((0, 0, img.width, 18), fill=(255, 255, 255))
    d.text((4, 3), title, fill=(0, 0, 0))
    x = img.width - 4
    for name, k in reversed(LEGEND):
        w = 8 * len(name) + 18
        x -= w
        d.rectangle((x, 4, x + 10, 14), outline=COLORS[k], width=3)
        d.text((x + 14, 3), name, fill=(0, 0, 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=88)
