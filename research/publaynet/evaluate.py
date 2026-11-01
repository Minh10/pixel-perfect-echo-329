"""Evaluate FINAUDIT AI's pretrained layout detector on a reproducible PubLayNet validation subset.

    python research/publaynet/evaluate.py \
        --val-json  <publaynet>/val.json \
        --image-dir <publaynet>/val \
        --model-dir <local snapshot of docling-project/docling-layout-heron> \
        --out research/publaynet/results [--n 200 --seed 20261101]

Outputs (in --out): publaynet_metrics.csv, publaynet_per_image_results.csv, timing.json, run_config.json,
subset_manifest.json, dataset_verification.json, visualizations/*.jpg.

No network access is used.  Nothing is estimated: if a stage cannot run, the script stops with the reason.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata as md
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from publaynet_eval import dataset as ds  # noqa: E402
from publaynet_eval import mapping  # noqa: E402
from publaynet_eval.metrics import coco_ap, match, prf, xywh_to_xyxy  # noqa: E402
from publaynet_eval.visualize import draw  # noqa: E402

PROD_THRESHOLD = 0.3  # docling 2.145.0 TransformersObjectDetectionEngineOptions.score_threshold default


def versions() -> dict:
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for p in ("docling", "docling-core", "docling-ibm-models", "transformers", "torch", "torchvision", "pillow",
              "numpy", "pycocotools"):
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


def model_files(model_dir: Path) -> dict[str, str]:
    return {p.name: ds.sha256_file(p) for p in sorted(model_dir.iterdir()) if p.is_file()}


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                              cwd=Path(__file__).parent).stdout.strip()
    except Exception:
        return None


def evaluate(coco: dict, subset: list[dict], image_dir: Path, run, id2label: dict[int, str], out: Path,
             iou_thr: float = 0.5, score_thr: float = PROD_THRESHOLD, n_vis: int = 24) -> dict:
    """`run(PIL image) -> Timed`.  Separated from model loading so the logic is testable offline."""
    from PIL import Image

    lab2cls = mapping.resolve(id2label)
    name2cat = {c["name"]: c["id"] for c in coco["categories"]}
    eval_classes = [*mapping.PRIMARY, *mapping.SECONDARY]
    by_img = ds.annotations_by_image(coco)
    totals = {c: {"gt": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0} for c in eval_classes}
    ignored_pred: dict[str, int] = {}
    per_image, detections, timings = [], [], {"preprocess_ms": [], "inference_ms": [], "postprocess_ms": []}
    for k, im in enumerate(subset):
        with Image.open(image_dir / im["file_name"]) as img:
            img.load()
            res = run(img)
            for key in timings:
                timings[key].append(getattr(res, key))
            row = {"image_id": im["id"], "file_name": im["file_name"], "width": im["width"], "height": im["height"],
                   "n_pred_all": len(res.detections), **{f"{t}_ms": round(getattr(res, f"{t}_ms"), 2)
                                                         for t in ("preprocess", "inference", "postprocess")}}
            vis = []
            for d in res.detections:
                cls = lab2cls.get(d.label)
                if cls is None:
                    ignored_pred[d.label] = ignored_pred.get(d.label, 0) + 1
                    continue
                x0, y0, x1, y1 = d.box
                detections.append({"image_id": im["id"], "category_id": name2cat[cls],
                                   "bbox": [x0, y0, x1 - x0, y1 - y0], "score": d.score})
            for cls in eval_classes:
                gts = [xywh_to_xyxy(a["bbox"]) for a in by_img.get(im["id"], []) if a["category_id"] == name2cat[cls]]
                preds = [(d.box, d.score, d.label) for d in res.detections
                         if lab2cls.get(d.label) == cls and d.score >= score_thr]
                m = match([(b, s) for b, s, _ in preds], gts, iou_thr)
                t = totals[cls]
                t["gt"] += len(gts)
                t["pred"] += len(preds)
                t["tp"] += len(m.tp)
                t["fp"] += len(m.fp)
                t["fn"] += len(m.fn)
                row.update({f"{cls}_gt": len(gts), f"{cls}_pred": len(preds), f"{cls}_tp": len(m.tp),
                            f"{cls}_fp": len(m.fp), f"{cls}_fn": len(m.fn)})
                if cls in mapping.PRIMARY:
                    vis += [{"kind": "gt", "box": g, "label": f"GT {cls}"} for g in gts]
                    vis += [{"kind": "tp", "box": preds[i][0], "label": preds[i][2], "score": preds[i][1]}
                            for i, _, _ in m.tp]
                    vis += [{"kind": "fp", "box": preds[i][0], "label": preds[i][2], "score": preds[i][1]}
                            for i in m.fp]
                    vis += [{"kind": "fn", "box": gts[j], "label": f"missed {cls}"} for j in m.fn]
            per_image.append(row)
            if k < n_vis:
                draw(img, vis, out / "visualizations" / f"{k:03d}_{Path(im['file_name']).stem}.jpg",
                     f"{im['file_name']}  table/figure @IoU{iou_thr}, score>={score_thr}")
    gt_sub = {"images": subset, "categories": coco["categories"],
              "annotations": [a for im in subset for a in by_img.get(im["id"], [])]}
    ap = coco_ap(gt_sub, detections, [name2cat[c] for c in eval_classes])
    metrics = []
    for cls in eval_classes:
        t = totals[cls]
        p, r, f = prf(t["tp"], t["fp"], t["fn"])
        a = ap[name2cat[cls]]
        metrics.append({"class": cls, "role": "primary" if cls in mapping.PRIMARY else "secondary",
                        "docling_labels": "+".join(mapping.PUBLAYNET_TO_DOCLING[cls]), **t,
                        "precision": p, "recall": r, "f1": f, "iou_threshold": iou_thr, "score_threshold": score_thr,
                        "coco_AP": a["AP"], "coco_AP50": a["AP50"], "coco_AP75": a["AP75"]})
    return {"metrics": metrics, "per_image": per_image, "timings": timings, "ignored_predictions": ignored_pred}


def write_csv(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def summarize_ms(xs: list[float]) -> dict:
    xs = sorted(xs)
    return {"n": len(xs), "mean": round(statistics.fmean(xs), 2), "p50": round(xs[len(xs) // 2], 2),
            "p95": round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 2)} if xs else {"n": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-json", type=Path, required=True)
    ap.add_argument("--image-dir", type=Path, required=True)
    ap.add_argument("--model-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261101)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--score-threshold", type=float, default=PROD_THRESHOLD)
    ap.add_argument("--ap-score-floor", type=float, default=0.01,
                    help="detector threshold used at inference so AP sees low-score boxes; P/R/F1 re-filter to --score-threshold")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--warmup", type=int, default=2)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    coco = ds.load_coco(args.val_json)
    ver = ds.verify_annotations(coco, args.val_json)
    subset = ds.select_subset(coco, args.n, args.seed)
    img_problems = [p for im in subset for p in ds.verify_image(im, args.image_dir)]
    (args.out / "dataset_verification.json").write_text(json.dumps(
        {**ver.__dict__, "subset_n": len(subset), "subset_image_problems": img_problems}, indent=1))
    if not ver.ok or img_problems:
        sys.exit(f"dataset verification failed; see {args.out / 'dataset_verification.json'}")
    ds.write_manifest(args.out / "subset_manifest.json", subset, args.image_dir, args.seed, ver.split_sha256)

    from PIL import Image

    from publaynet_eval.detector import LayoutDetector

    det = LayoutDetector(args.model_dir, score_threshold=min(args.ap_score_floor, args.score_threshold),
                         device=args.device, num_threads=args.threads)
    for im in subset[: args.warmup]:  # warm-up runs are timed separately and excluded
        with Image.open(args.image_dir / im["file_name"]) as img:
            det(img)
    res = evaluate(coco, subset, args.image_dir, det, det.id2label, args.out, args.iou, args.score_threshold)
    write_csv(args.out / "publaynet_metrics.csv", res["metrics"])
    write_csv(args.out / "publaynet_per_image_results.csv", res["per_image"])
    (args.out / "timing.json").write_text(json.dumps(
        {"model_init_ms": round(det.init_ms, 1), "warmup_images": args.warmup,
         **{k: summarize_ms(v) for k, v in res["timings"].items()},
         "note": "preprocess = RGB conversion + HF image processor; inference = model forward under inference_mode; "
                 "postprocess = post_process_object_detection; JPEG decoding and model loading excluded"}, indent=1))
    (args.out / "run_config.json").write_text(json.dumps(
        {"args": {k: str(v) for k, v in vars(args).items()}, "versions": versions(), "git_commit": git_commit(),
         "model_config_id2label": det.id2label, "model_files_sha256": model_files(args.model_dir),
         "label_mapping": mapping.PUBLAYNET_TO_DOCLING, "not_evaluated": mapping.NOT_EVALUATED,
         "ignored_prediction_labels": res["ignored_predictions"]}, indent=1))
    for m in res["metrics"]:
        print(m)


if __name__ == "__main__":
    main()
