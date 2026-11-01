# Final limitations

Checked on 1 November 2026. This is a local short-course demonstration on a synthetic PDF. It is not a production audit system.

## Chart summary and discrepancy

- No LLM or vision provider is configured. Chart reading and question answering return HTTP 503. The UI does not fill in a summary.
- The figure crop and the caption "Figure 1: Revenue by segment, 2025 (synthetic)" come from Docling. The bar heights were not converted into numbers.
- Docling OCR is off. The visible axis labels North, South, East, and West are part of the crop image. They are not a separate OCR transcript.
- Retrieval text for the figure says the figure values are not extracted from the image. The sentence "North remained the largest segment, contributing 50% of Group revenue" is narrative text beside the figure.
- Visual check remains INSUFFICIENT_EVIDENCE until a real chart reading is stored. MATCH and POTENTIAL_DISCREPANCY were not produced from this PDF.

## Trend comparison

- Plotted numbers are parsed table cells only. The Change column is a percent and is left out of the amount comparison.
- The two reports used for the chart are copies of `services/api/tests/fixtures/annual_report_excerpt.pdf`. Matching bars mean the same fixture was processed more than once. They are not two issuers and not a comprehensive trend.
- Scope on these facts is `unknown`. Period type is `unknown`. The years 2024 and 2025 come from the column headers.
- The income-statement retrieval text can contain the broken fragment "Units: re presented". The highlighted table shows the parsed cells, including operating profit 703.

## Upload and vectors

- The acceptance upload was parsed successfully while the API and worker were both running. Its index run stored 0 vectors because the local Qdrant files were already open in the API process. A hybrid search of that new report still returned the page-2 table and the operating-profit sentence. That does not mean new vectors were written.
- To rebuild vectors, stop the API and the worker, then from `services\api` run:

```powershell
.\.venv\Scripts\python.exe -c @"
from app.config import get_settings
from app.storage.db import Repository
from app.storage.files import FileStore
from app.indexing.store import ChunkStore
from app.indexing.service import index_document
s = get_settings()
repo = Repository(s.db_path)
files = FileStore(s.documents_dir)
chunks = ChunkStore(s.db_path)
for d in repo.list_documents():
    if d.get('status') != 'ready':
        continue
    print(d['id'], index_document(d, files, chunks, s))
"@
```

Start the API, then the worker.

## Corpus and deployment

- PubLayNet was not used.
- The API has no authentication. It listens on `127.0.0.1:8000` only. Do not publish it and do not merge this branch to `main`.
- Uploaded PDFs, SQLite, and model weights under `services/api/data` and `services/api/models` stay out of git.
- A fresh parse of this fixture took 103.3 seconds after Docling loaded its layout model. Do not rely on a cold upload inside a five-minute demonstration.
