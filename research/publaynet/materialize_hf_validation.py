"""Build a COCO val.json and the JPEGs the harness needs from the Hugging Face validation split.

The IBM DAX host (dax-cdn.cdn.appdomain.cloud) did not resolve on this machine. The validation
split of creative-graphic-design/PubLayNet is the published PubLayNet validation set (11,245
pages) and keeps the original COCO image ids, file names, boxes and category ids. Training
shards are not read.

    python research/publaynet/materialize_hf_validation.py \
        --parquet-dir C:/Users/Lenovo/data/publaynet-hf/data \
        --out C:/Users/Lenovo/data/publaynet \
        --n 20 --n 200 --seed 20261101
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from publaynet_eval.dataset import EXPECTED_CATEGORIES, select_subset

NAME_INDEX_TO_ID = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1 << 20):
            h.update(block)
    return h.hexdigest()


def iter_meta(parquet_dir: Path):
    files = sorted(parquet_dir.glob("validation-*.parquet"))
    if not files:
        raise SystemExit(f"no validation parquet files in {parquet_dir}")
    for path in files:
        pf = pq.ParquetFile(path)
        for rg in range(pf.num_row_groups):
            # Projecting category.name beside category_id drops the name field, so the
            # whole annotation struct is read. Segmentation payloads in this export are
            # empty; the image bytes column is not.
            table = pf.read_row_group(
                rg,
                columns=["image_id", "file_name", "width", "height", "annotations"],
            )
            rows = table.to_pydict()
            ann = rows["annotations"]
            for i in range(table.num_rows):
                yield path.name, rows["image_id"][i], rows["file_name"][i], rows["width"][i], rows["height"][i], ann[i]


def build(parquet_dir: Path, out: Path, sizes: list[int], seed: int) -> None:
    images, annotations = [], []
    seen_images, seen_ann = set(), set()
    problems = []
    dropped_nonpositive = []
    cat_counts = {name: 0 for name in EXPECTED_CATEGORIES.values()}
    id_to_name = {i: n for i, n in EXPECTED_CATEGORIES.items()}
    for _src, image_id, file_name, width, height, ann in iter_meta(parquet_dir):
        if image_id in seen_images:
            problems.append(f"duplicate image_id {image_id}")
            continue
        seen_images.add(image_id)
        images.append({"id": int(image_id), "file_name": file_name, "width": int(width), "height": int(height)})
        ids = ann["annotation_id"]
        boxes = ann["bbox"]
        cids = ann["category_id"]
        nested = ann["category"]
        crowds = ann["iscrowd"]
        for j, (aid, box, cid, crowd) in enumerate(zip(ids, boxes, cids, crowds)):
            nested_id = nested[j]["category_id"]
            name_index = int(nested[j]["name"])
            if cid != nested_id or NAME_INDEX_TO_ID.get(name_index) != int(cid):
                problems.append(f"image {image_id} ann {aid}: category_id {cid} nested {nested_id} name {name_index}")
                continue
            if int(cid) not in EXPECTED_CATEGORIES:
                problems.append(f"image {image_id} ann {aid}: unknown category {cid}")
                continue
            if float(box[2]) <= 0 or float(box[3]) <= 0:
                # evaluate.py stops if any box has a non-positive side. Record and exclude them.
                dropped_nonpositive.append({"id": int(aid), "image_id": int(image_id), "category_id": int(cid),
                                            "bbox": [float(v) for v in box]})
                continue
            if aid in seen_ann:
                problems.append(f"duplicate annotation_id {aid}")
                continue
            seen_ann.add(aid)
            cat_counts[id_to_name[int(cid)]] += 1
            annotations.append({
                "id": int(aid),
                "image_id": int(image_id),
                "category_id": int(cid),
                "bbox": [float(v) for v in box],
                "area": float(box[2]) * float(box[3]),
                "iscrowd": 1 if crowd else 0,
            })
    if problems:
        raise SystemExit("category/id problems:\n" + "\n".join(problems[:30]))
    coco = {
        "info": {
            "description": "PubLayNet validation split reconstructed from creative-graphic-design/PubLayNet",
            "revision": "4bfc1ae32abdad8953c0b81e5cdf236f1745de50",
            "note": "Original COCO image ids, file names, boxes and category ids. Training split was not downloaded.",
        },
        "images": images,
        "annotations": annotations,
        "categories": [{"id": i, "name": n, "supercategory": "layout"} for i, n in EXPECTED_CATEGORIES.items()],
    }
    out.mkdir(parents=True, exist_ok=True)
    val_json = out / "val.json"
    val_json.write_text(json.dumps(coco))
    wanted = {}
    for n in sizes:
        for im in select_subset(coco, n, seed):
            wanted[im["file_name"]] = im
    image_dir = out / "val"
    image_dir.mkdir(exist_ok=True)
    remaining = set(wanted)
    for path in sorted(parquet_dir.glob("validation-*.parquet")):
        if not remaining:
            break
        pf = pq.ParquetFile(path)
        for rg in range(pf.num_row_groups):
            if not remaining:
                break
            table = pf.read_row_group(rg, columns=["file_name", "image"])
            names = table.column("file_name").to_pylist()
            blobs = table.column("image").to_pylist()
            for name, blob in zip(names, blobs):
                if name not in remaining:
                    continue
                raw = blob["bytes"]
                if not raw or raw[:2] != b"\xff\xd8":
                    raise SystemExit(f"{name} is not a JPEG payload")
                (image_dir / name).write_bytes(raw)
                remaining.remove(name)
    if remaining:
        raise SystemExit(f"missing JPEGs: {sorted(remaining)[:10]}")
    archives = []
    for path in sorted(parquet_dir.glob("validation-*.parquet")):
        archives.append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    provenance = {
        "source": "huggingface.co/datasets/creative-graphic-design/PubLayNet",
        "revision": "4bfc1ae32abdad8953c0b81e5cdf236f1745de50",
        "split": "validation",
        "ibm_dax": "dax-cdn.cdn.appdomain.cloud did not resolve (curl exit 6); training archive was not downloaded",
        "n_images": len(images),
        "n_annotations": len(annotations),
        "dropped_nonpositive_boxes": dropped_nonpositive,
        "category_counts": cat_counts,
        "val_json_sha256": sha256_file(val_json),
        "extracted_images": len(wanted),
        "seed": seed,
        "subset_sizes": sizes,
        "parquet": archives,
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1))
    print(json.dumps({k: provenance[k] for k in ("n_images", "n_annotations", "category_counts", "val_json_sha256", "extracted_images")}, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, action="append", default=[])
    ap.add_argument("--seed", type=int, default=20261101)
    args = ap.parse_args()
    build(args.parquet_dir, args.out, args.n or [200], args.seed)


if __name__ == "__main__":
    main()
