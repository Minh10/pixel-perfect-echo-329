"""IoU matching, per-class precision / recall / F1, and (optionally) COCO AP via pycocotools.

Matching (per image, per class): predictions sorted by score (desc), each matched greedily to the unmatched
ground-truth box with the highest IoU >= threshold; one-to-one.  This is the standard detection matching used
by VOC/COCO at a single IoU threshold, applied to the boxes kept after the detector's score threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

Box = tuple[float, float, float, float]  # x0, y0, x1, y1 (pixels)


def xywh_to_xyxy(b: list[float]) -> Box:
    x, y, w, h = b
    return (x, y, x + w, y + h)


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class MatchResult:
    tp: list[tuple[int, int, float]]  # (pred index, gt index, iou)
    fp: list[int]
    fn: list[int]


def match(preds: list[tuple[Box, float]], gts: list[Box], thr: float = 0.5) -> MatchResult:
    order = sorted(range(len(preds)), key=lambda i: -preds[i][1])
    used: set[int] = set()
    tp, fp = [], []
    for i in order:
        best, best_j = 0.0, -1
        for j, g in enumerate(gts):
            if j in used:
                continue
            v = iou(preds[i][0], g)
            if v > best:
                best, best_j = v, j
        if best_j >= 0 and best >= thr:
            used.add(best_j)
            tp.append((i, best_j, best))
        else:
            fp.append(i)
    fn = [j for j in range(len(gts)) if j not in used]
    return MatchResult(tp=tp, fp=fp, fn=fn)


def prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p is not None and r is not None and p + r > 0 else (0.0 if p is not None and r is not None else None)
    return p, r, f


def coco_ap(gt_coco: dict, detections: list[dict], cat_ids: list[int]) -> dict[int, dict[str, float]]:
    """Official COCOeval per category (AP@[.5:.95], AP50, AP75).  `detections` need real model scores."""
    import contextlib
    import io

    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    gt = COCO()
    gt.dataset = gt_coco
    with contextlib.redirect_stdout(io.StringIO()):
        gt.createIndex()
        dt = gt.loadRes(detections) if detections else None
    out: dict[int, dict[str, float]] = {}
    for cid in cat_ids:
        if dt is None:
            out[cid] = {"AP": float("nan"), "AP50": float("nan"), "AP75": float("nan")}
            continue
        ev = COCOeval(gt, dt, "bbox")
        ev.params.catIds = [cid]
        ev.params.imgIds = sorted({im["id"] for im in gt_coco["images"]})
        with contextlib.redirect_stdout(io.StringIO()):
            ev.evaluate()
            ev.accumulate()
            ev.summarize()
        out[cid] = {"AP": float(ev.stats[0]), "AP50": float(ev.stats[1]), "AP75": float(ev.stats[2])}
    return out
