#!/usr/bin/env bash
# Fetch ONLY what the evaluation needs: PubLayNet validation images + annotations, and the Docling layout model.
# Run where huggingface.co and dax-cdn.cdn.appdomain.cloud are reachable (both were denied by the network
# policy of the environment that wrote this script, so these URLs have NOT been verified from here).
#
#   bash research/publaynet/fetch_inputs.sh <data-dir> [model-revision]
#
# PubLayNet URLs are those listed in the PubLayNet project README (IBM Data Asset eXchange). The full archive is
# ~96 GB; the per-split val archive is used instead so the training images are never downloaded.
set -euo pipefail
DATA=${1:?data dir}
REV=${2:-main}   # pass a commit SHA to pin; the resolved SHA is recorded either way
mkdir -p "$DATA"
BASE=https://dax-cdn.cdn.appdomain.cloud/dax-publaynet/1.0.0
for f in labels.tar.gz val.tar.gz; do
  [ -f "$DATA/$f" ] || curl -fL --retry 3 -o "$DATA/$f" "$BASE/$f"
done
tar -xzf "$DATA/labels.tar.gz" -C "$DATA"
tar -xzf "$DATA/val.tar.gz" -C "$DATA"
( cd "$DATA" && sha256sum labels.tar.gz val.tar.gz > archives.sha256 )

python - "$DATA" "$REV" <<'EOF'
import json, sys
from huggingface_hub import snapshot_download, HfApi
data, rev = sys.argv[1], sys.argv[2]
info = HfApi().model_info("docling-project/docling-layout-heron", revision=rev)
path = snapshot_download("docling-project/docling-layout-heron", revision=info.sha,
                         local_dir=f"{data}/docling-layout-heron")
json.dump({"repo_id": "docling-project/docling-layout-heron", "requested_revision": rev, "resolved_sha": info.sha,
           "local_dir": path}, open(f"{data}/model_revision.json", "w"), indent=1)
print("model at", path, "revision", info.sha)
EOF
