"""The layout detector FINAUDIT AI uses, run directly on page images.

FINAUDIT's Docling parser (`services/api/app/processing/docling_parser.py`) builds a `DocumentConverter` with
default layout options.  For docling 2.145.0 the default is `LayoutObjectDetectionOptions`:

    model_spec  = docling-project/docling-layout-heron  (revision "main" -- NOT pinned by Docling)
    engine      = TransformersObjectDetectionEngineOptions(score_threshold=0.3, torch_dtype=None, compile=False)

The engine (`docling/models/inference_engines/object_detection/transformers_engine.py`) does:
    processor = AutoImageProcessor from the model folder; model = AutoModelForObjectDetection
    inputs = processor(images=[img.convert("RGB")]); target_sizes = [[h, w]]
    with torch.inference_mode(): outputs = model(**inputs)
    processor.post_process_object_detection(outputs, target_sizes, threshold=score_threshold)

`LayoutDetector` reproduces exactly those calls, so its boxes are the raw detector output in the input
image's pixel frame -- the same frame as PubLayNet's COCO boxes.  It does NOT run Docling's layout
post-processing (cluster merging, cell assignment, reading order), which needs PDF text cells and is what
the full `DocumentConverter` adds on top.  Timings are split into init, preprocess, inference, postprocess.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Detection:
    label: str
    score: float
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in image pixels


@dataclass
class Timed:
    detections: list[Detection]
    preprocess_ms: float
    inference_ms: float
    postprocess_ms: float


class LayoutDetector:
    def __init__(self, model_dir: Path, score_threshold: float = 0.3, device: str = "cpu", num_threads: int = 4):
        t0 = time.perf_counter()
        import torch
        from transformers import AutoImageProcessor, AutoModelForObjectDetection

        torch.set_num_threads(num_threads)
        self.torch = torch
        self.device = torch.device(device)
        self.model_dir = Path(model_dir)
        self.config = json.loads((self.model_dir / "config.json").read_text())
        self.id2label = {int(k): v for k, v in self.config["id2label"].items()}
        self.processor = AutoImageProcessor.from_pretrained(str(self.model_dir))
        self.model = AutoModelForObjectDetection.from_pretrained(str(self.model_dir)).to(self.device).eval()
        self.score_threshold = score_threshold
        self.init_ms = (time.perf_counter() - t0) * 1000

    def __call__(self, image) -> Timed:
        torch = self.torch
        t0 = time.perf_counter()
        img = image.convert("RGB")
        inputs = self.processor(images=[img], return_tensors="pt").to(self.device, self.model.dtype)
        target_sizes = torch.tensor([[img.height, img.width]], device=self.device)
        t1 = time.perf_counter()
        with torch.inference_mode():
            outputs = self.model(**inputs)
        t2 = time.perf_counter()
        res = self.processor.post_process_object_detection(outputs, target_sizes=target_sizes,
                                                           threshold=self.score_threshold)[0]
        dets = [Detection(label=self.id2label[int(lid)].lower(), score=float(s), box=tuple(float(v) for v in b))
                for lid, s, b in zip(res["labels"].tolist(), res["scores"].tolist(), res["boxes"].tolist())]
        t3 = time.perf_counter()
        return Timed(dets, (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000)
