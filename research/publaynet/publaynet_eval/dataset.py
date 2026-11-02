"""PubLayNet validation-split loading, verification and reproducible subset selection.

PubLayNet (Zhong et al., ICDAR 2019) ships COCO-format annotations per split (`val.json`) and JPEG page images.
Boxes are COCO `[x, y, width, height]` in image pixels, origin top-left.  Official categories:
1 text, 2 title, 3 list, 4 table, 5 figure.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

EXPECTED_CATEGORIES = {1: "text", 2: "title", 3: "list", 4: "table", 5: "figure"}


@dataclass
class Verification:
    split_file: str
    split_sha256: str
    n_images: int
    n_annotations: int
    categories: dict[int, str]
    category_counts: dict[str, int]
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def load_coco(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def verify_annotations(coco: dict, split_file: Path) -> Verification:
    """Structural checks on the COCO file itself (no images needed)."""
    cats = {c["id"]: c["name"] for c in coco.get("categories", [])}
    problems = []
    if cats != EXPECTED_CATEGORIES:
        problems.append(f"categories {cats} differ from the published PubLayNet set {EXPECTED_CATEGORIES}")
    images = {im["id"]: im for im in coco.get("images", [])}
    counts = {name: 0 for name in cats.values()}
    for a in coco.get("annotations", []):
        im = images.get(a["image_id"])
        if im is None:
            problems.append(f"annotation {a.get('id')} references unknown image {a['image_id']}")
            continue
        x, y, w, h = a["bbox"]
        if w <= 0 or h <= 0:
            problems.append(f"annotation {a.get('id')}: non-positive size {a['bbox']}")
        if x < -1 or y < -1 or x + w > im["width"] + 1 or y + h > im["height"] + 1:
            problems.append(f"annotation {a.get('id')}: box {a['bbox']} outside image {im['width']}x{im['height']}")
        counts[cats.get(a["category_id"], f"unknown:{a['category_id']}")] = counts.get(
            cats.get(a["category_id"], f"unknown:{a['category_id']}"), 0) + 1
    return Verification(split_file=split_file.name, split_sha256=sha256_file(split_file), n_images=len(images),
                        n_annotations=len(coco.get("annotations", [])), categories=cats, category_counts=counts,
                        problems=problems[:50])


def verify_image(im: dict, image_dir: Path) -> list[str]:
    """Checks that the JPEG exists and that its pixel size equals the COCO width/height."""
    from PIL import Image

    p = image_dir / im["file_name"]
    if not p.exists():
        return [f"{im['file_name']}: missing"]
    with Image.open(p) as img:
        if img.size != (im["width"], im["height"]):
            return [f"{im['file_name']}: file is {img.size[0]}x{img.size[1]}, COCO says {im['width']}x{im['height']}"]
    return []


def select_subset(coco: dict, n: int, seed: int) -> list[dict]:
    """Deterministic: sort image records by id, then `random.Random(seed).sample`.  Depends only on the JSON."""
    images = sorted(coco["images"], key=lambda im: im["id"])
    if n >= len(images):
        return images
    picked = random.Random(seed).sample(images, n)
    return sorted(picked, key=lambda im: im["id"])


def annotations_by_image(coco: dict) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for a in coco["annotations"]:
        out.setdefault(a["image_id"], []).append(a)
    return out


def write_manifest(path: Path, subset: list[dict], image_dir: Path | None, seed: int, split_sha: str) -> None:
    rows = []
    for im in subset:
        p = image_dir / im["file_name"] if image_dir else None
        rows.append({"id": im["id"], "file_name": im["file_name"], "width": im["width"], "height": im["height"],
                     "sha256": sha256_file(p) if p and p.exists() else None})
    path.write_text(json.dumps({"seed": seed, "n": len(subset), "split_sha256": split_sha, "images": rows}, indent=1))
