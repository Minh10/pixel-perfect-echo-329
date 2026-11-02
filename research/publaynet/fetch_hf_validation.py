"""Download only the PubLayNet validation parquet shards.

The IBM DAX host used by fetch_inputs.sh did not resolve on the machine that ran the
evaluation (curl exit 6). This script uses Hugging Face and does not fetch the training split.

    python research/publaynet/fetch_hf_validation.py C:/Users/Lenovo/data/publaynet-hf
"""

from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

REVISION = "4bfc1ae32abdad8953c0b81e5cdf236f1745de50"


def main() -> None:
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "publaynet-hf")
    path = snapshot_download(
        repo_id="creative-graphic-design/PubLayNet",
        repo_type="dataset",
        revision=REVISION,
        allow_patterns=["data/validation-*.parquet", "README.md"],
        local_dir=str(dest),
    )
    print(path)


if __name__ == "__main__":
    main()
