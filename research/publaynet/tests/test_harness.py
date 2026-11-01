"""Offline tests of the evaluation harness logic.

Uses a tiny SYNTHETIC COCO dataset and a scripted detector double.  These tests verify the matching, metric,
mapping, dataset-verification, subset-selection, CSV and visualisation code paths only.  They produce NO
evaluation result about the real model or PubLayNet.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[1]))

import evaluate as ev  # noqa: E402
from publaynet_eval import dataset as ds  # noqa: E402
from publaynet_eval import mapping  # noqa: E402
from publaynet_eval.detector import Detection, Timed  # noqa: E402
from publaynet_eval.metrics import iou, match, prf, xywh_to_xyxy  # noqa: E402

CATS = [{"id": i, "name": n} for i, n in ds.EXPECTED_CATEGORIES.items()]
# Docling-style vocabulary for the double (the real one is read from the model's config.json at run time)
ID2LABEL = {0: "caption", 1: "footnote", 2: "formula", 3: "list_item", 4: "page_footer", 5: "page_header",
            6: "picture", 7: "section_header", 8: "table", 9: "text", 10: "title"}


@pytest.fixture
def synth(tmp_path: Path):
    imgdir = tmp_path / "val"
    imgdir.mkdir()
    images, anns = [], []
    for i in range(1, 4):
        Image.new("RGB", (200, 300), "white").save(imgdir / f"p{i}.jpg")
        images.append({"id": i, "file_name": f"p{i}.jpg", "width": 200, "height": 300})
    anns += [{"id": 1, "image_id": 1, "category_id": 4, "bbox": [10, 10, 100, 50], "area": 5000, "iscrowd": 0},
             {"id": 2, "image_id": 1, "category_id": 5, "bbox": [10, 100, 80, 80], "area": 6400, "iscrowd": 0},
             {"id": 3, "image_id": 2, "category_id": 4, "bbox": [20, 20, 150, 100], "area": 15000, "iscrowd": 0},
             {"id": 4, "image_id": 3, "category_id": 1, "bbox": [10, 10, 180, 40], "area": 7200, "iscrowd": 0},
             {"id": 5, "image_id": 3, "category_id": 3, "bbox": [10, 100, 180, 60], "area": 10800, "iscrowd": 0}]
    coco = {"images": images, "annotations": anns, "categories": CATS}
    (tmp_path / "val.json").write_text(json.dumps(coco))
    return tmp_path, coco, imgdir


def scripted(dets_by_file):
    def run(img):
        return Timed(dets_by_file[Path(img.filename).name], 1.0, 2.0, 0.5)
    return run


def test_iou_and_greedy_one_to_one_matching() -> None:
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)
    gts = [(0, 0, 10, 10)]
    m = match([((0, 0, 10, 10), 0.9), ((0, 0, 10, 9), 0.95)], gts, 0.5)
    assert len(m.tp) == 1 and m.tp[0][0] == 1 and m.fp == [0] and m.fn == []  # higher score wins, duplicate = FP
    m = match([((50, 50, 60, 60), 0.9)], gts, 0.5)
    assert m.fp == [0] and m.fn == [0]
    assert xywh_to_xyxy([10, 20, 30, 40]) == (10, 20, 40, 60)


def test_prf_handles_empty_cases() -> None:
    assert prf(0, 0, 0) == (None, None, None)
    assert prf(3, 1, 0) == (0.75, 1.0, pytest.approx(6 / 7))
    assert prf(0, 2, 2) == (0.0, 0.0, 0.0)


def test_mapping_requires_model_vocabulary() -> None:
    lab2cls = mapping.resolve(ID2LABEL)
    assert lab2cls["picture"] == "figure" and lab2cls["table"] == "table" and lab2cls["section_header"] == "title"
    assert "list_item" not in lab2cls and "page_header" not in lab2cls
    with pytest.raises(ValueError):
        mapping.resolve({0: "table", 1: "text"})


def test_dataset_verification_and_deterministic_subset(synth) -> None:
    root, coco, imgdir = synth
    v = ds.verify_annotations(coco, root / "val.json")
    assert v.ok and v.category_counts["table"] == 2
    bad = dict(coco, categories=[{"id": 1, "name": "paragraph"}])
    assert not ds.verify_annotations(bad, root / "val.json").ok
    assert ds.select_subset(coco, 2, 7) == ds.select_subset(coco, 2, 7)
    assert all(not ds.verify_image(im, imgdir) for im in coco["images"])
    wrong = dict(coco["images"][0], width=999)
    assert "COCO says" in ds.verify_image(wrong, imgdir)[0]


def test_end_to_end_with_scripted_detector(synth, tmp_path: Path) -> None:
    root, coco, imgdir = synth
    dets = {
        "p1.jpg": [Detection("table", 0.9, (10, 10, 110, 60)),           # TP table
                   Detection("picture", 0.8, (100, 200, 150, 250)),     # FP figure (wrong place) -> GT figure FN
                   Detection("page_header", 0.9, (0, 0, 200, 8))],      # ignored label
        "p2.jpg": [Detection("table", 0.2, (20, 20, 170, 120))],         # below 0.3 -> not counted -> FN
        "p3.jpg": [Detection("text", 0.7, (10, 10, 190, 50)),            # TP text
                   Detection("list_item", 0.9, (10, 100, 190, 130))],   # list not evaluated
    }
    out = tmp_path / "out"
    res = ev.evaluate(coco, coco["images"], imgdir, scripted(dets), ID2LABEL, out)
    m = {r["class"]: r for r in res["metrics"]}
    assert (m["table"]["tp"], m["table"]["fp"], m["table"]["fn"]) == (1, 0, 1)
    assert (m["figure"]["tp"], m["figure"]["fp"], m["figure"]["fn"]) == (0, 1, 1)
    assert m["text"]["tp"] == 1 and m["title"]["gt"] == 0
    assert res["ignored_predictions"] == {"page_header": 1, "list_item": 1}
    # AP uses ALL scores (incl. the 0.2 table), so table AP50 = 1.0 here while recall@0.3 = 0.5
    assert m["table"]["coco_AP50"] == pytest.approx(1.0)
    assert len(list((out / "visualizations").glob("*.jpg"))) == 3
    ev.write_csv(out / "m.csv", res["metrics"])
    assert next(csv.DictReader(open(out / "m.csv")))["class"] == "table"


def test_detector_plumbing_with_random_untrained_model(tmp_path: Path) -> None:
    """Exercises LayoutDetector's load/preprocess/infer/postprocess path and its coordinate frame using a TINY
    RANDOMLY INITIALISED RT-DETRv2 built locally (no download).  Its detections are meaningless by design."""
    transformers = pytest.importorskip("transformers")
    from publaynet_eval.detector import LayoutDetector

    cfg = transformers.RTDetrV2Config(
        id2label=ID2LABEL, label2id={v: k for k, v in ID2LABEL.items()}, num_queries=20, d_model=32,
        encoder_hidden_dim=32, encoder_ffn_dim=64, decoder_ffn_dim=64, decoder_layers=2, encoder_layers=1,
        num_feature_levels=3, decoder_n_points=2, use_pretrained_backbone=False,
        encoder_in_channels=[32, 64, 128], decoder_in_channels=[32, 32, 32], feat_strides=[8, 16, 32],
        backbone_config=transformers.RTDetrResNetConfig(embedding_size=16, hidden_sizes=[16, 32, 64, 128],
                                                         depths=[1, 1, 1, 1], out_features=["stage2", "stage3", "stage4"]))
    transformers.RTDetrV2ForObjectDetection(cfg).save_pretrained(tmp_path)
    transformers.RTDetrImageProcessor(size={"height": 160, "width": 160}).save_pretrained(tmp_path)
    det = LayoutDetector(tmp_path, score_threshold=0.0, num_threads=1)
    assert det.init_ms > 0 and det.id2label[8] == "table"
    res = det(Image.new("RGB", (612, 792), "white"))  # non-square page: boxes must come back in THIS frame
    assert res.detections and all(d.label in ID2LABEL.values() for d in res.detections)
    for d in res.detections:
        x0, y0, x1, y1 = d.box
        assert -1 <= x0 <= x1 <= 613 and -1 <= y0 <= y1 <= 793
    assert res.inference_ms > 0 and res.preprocess_ms > 0
