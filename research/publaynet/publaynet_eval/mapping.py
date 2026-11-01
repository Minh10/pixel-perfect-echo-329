"""Class mapping between PubLayNet categories and Docling (DocLayNet-style) layout labels.

Only semantically compatible classes are evaluated.  Table and Figure are the primary targets.

| PubLayNet | Docling label(s)                 | Evaluated | Why |
|-----------|----------------------------------|-----------|-----|
| table     | table                            | primary   | same concept: the tabular region (PubLayNet's table box excludes the caption) |
| figure    | picture                          | primary   | same concept: graphical region; PubLayNet calls it figure, Docling picture |
| title     | title, section_header            | secondary | PubLayNet "title" covers article title AND section headings; Docling splits them |
| text      | text, caption, footnote, formula | secondary | PubLayNet folds captions/footnotes/display text into "text"; Docling separates them |
| list      | list_item                        | NOT evaluated | granularity mismatch: PubLayNet boxes a whole list, Docling boxes each item |
| (none)    | page_header, page_footer, code, checkbox_*, form, key_value_region, document_index | ignored | PubLayNet does not annotate these; predictions of them are neither TP nor FP |

The Docling label strings are NOT hard-coded as the model's vocabulary: the detector's `config.json` `id2label`
is read at run time and every mapped label must exist in it (see `resolve`), so a model whose vocabulary
differs fails loudly instead of being silently mis-scored.
"""

from __future__ import annotations

PRIMARY = ("table", "figure")
SECONDARY = ("title", "text")

# PubLayNet class -> Docling labels whose predictions count as that class
PUBLAYNET_TO_DOCLING: dict[str, tuple[str, ...]] = {
    "table": ("table",),
    "figure": ("picture",),
    "title": ("title", "section_header"),
    "text": ("text", "caption", "footnote", "formula"),
}
NOT_EVALUATED = {"list": "PubLayNet boxes whole lists; Docling boxes list items (granularity mismatch)"}


def resolve(id2label: dict[int, str]) -> dict[str, str]:
    """Return {docling_label: publaynet_class} for the evaluated classes; raise if the model lacks a label."""
    vocab = {v.lower() for v in id2label.values()}
    out: dict[str, str] = {}
    missing = []
    for cls, labels in PUBLAYNET_TO_DOCLING.items():
        for lab in labels:
            if lab in vocab:
                out[lab] = cls
            else:
                missing.append(lab)
    if missing:
        raise ValueError(f"model vocabulary {sorted(vocab)} lacks mapped labels {missing}; update mapping.py")
    return out
