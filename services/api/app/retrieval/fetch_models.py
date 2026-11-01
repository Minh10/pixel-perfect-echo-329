"""Fetch the default local embedding model (checksum-pinned).

    python -m app.retrieval.fetch_models [--dest models/all-MiniLM-L6-v2]

Source: ONNX export of sentence-transformers/all-MiniLM-L6-v2 (Apache-2.0) as published by the Chroma
project.  It is used because it is reachable without HuggingFace; any ONNX sentence encoder with a
`tokenizer.json` works via FINAUDIT_EMBEDDER_MODEL_PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import tarfile
import urllib.request
from pathlib import Path

URL = "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
WANTED = {"model.onnx", "tokenizer.json", "config.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt"}


def fetch(dest: Path) -> Path:
    if (dest / "model.onnx").exists() and (dest / "tokenizer.json").exists():
        return dest
    with urllib.request.urlopen(URL, timeout=600) as r:  # noqa: S310 - pinned https URL + checksum
        blob = r.read()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != SHA256:
        raise SystemExit(f"checksum mismatch: {digest} != {SHA256}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        for m in tf.getmembers():
            name = Path(m.name).name
            if m.isfile() and name in WANTED:  # flatten; ignore anything unexpected (no path traversal)
                (dest / name).write_bytes(tf.extractfile(m).read())  # type: ignore[union-attr]
    return dest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, default=Path("models/all-MiniLM-L6-v2"))
    print("model at", fetch(ap.parse_args().dest))


if __name__ == "__main__":
    main()
