# Fix errors, speed up, and simplify the Report workspace

Changes affect only screens. The Windows document service, sign-in, and limits stay as they are.

## 1. Fix visible errors (from screenshot)
- **Broken page thumbnails** (left column shows broken image icons). First step: check in the live session why small page images fail (likely the size option added to the image address is rejected or the address is built wrong). Fix it; if a thumbnail still fails, show a neat placeholder instead of a broken icon.
- **"0×0 table" entries**: hide the empty size text, show "Table (structure not extracted)".
- **Repeated "Figure region (no caption detected…)"**: group duplicates per page ("3 figures on page 10") so the list is readable.

## 2. Faster
- Thumbnails load only when scrolled into view (lazy) and at small size.
- Main page image: show a soft skeleton while loading; preload next page.
- Keep tool panels (Ask, Chart checks, Statistics) unloaded until first opened; cache report data so switching pages/tools does not refetch.
- Measure page load before/after in the browser and report numbers.

## 3. Simpler to use
- One clear toolbar: page controls + Source PDF; move zoom, Highlights and panel toggles into a single "View" menu.
- Rename tools to plain words with a one-line hint: **Evidence** (what was found), **Ask** (question the PDF), **Charts** (summaries & checks), **Trends** (compare years).
- Evidence list: filter chips (All / Tables / Charts / Metrics) at top, items for the current page shown first, clicking an item jumps to it on the page.
- Notice banner shrinks to a small "13 notices" chip that opens details.
- First-visit 3-step hint ("Pick a page → click evidence → ask a question"), dismissible.

## Verification
- Live demo session at 1280 and 1069 widths: thumbnails render, no broken images, no console errors, tools switch, tests/lint/build pass. Not published until you confirm.

## Technical notes
- Files: page-navigator.tsx, document-page.tsx, intelligence.tsx, evidence inspector component, styles. Use `loading="lazy"`, `onError` fallback, proxy query allowlist check for `dpi`.
