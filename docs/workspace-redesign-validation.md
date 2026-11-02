# PDF workspace redesign — 2026-11-02

## Presentation changes

- Report-first 65/35 resizable desktop reader, neutral canvas, independent scrolling and collapsible inspector.
- Collapsed desktop app navigation; Pages opens an overlay rather than a permanent third column.
- Compact title/page/view toolbar with accessible named icon controls. Fit Width follows canvas width; Fit Page follows width and height. Explicit zoom/highlight preferences persist per report in tab storage.
- Default Overview derives document metadata, page outline, region/table counts and current-page context only from loaded service values.
- Evidence grouped by page/type with exact selection, table/crop details, available provenance and existing FastAPI Read chart action. Selection is preserved in URL and highlights the linked PDF region.
- Existing QA, audit and multi-report comparison panels retain their services and stay mounted once visited. No permanent quick-start banner or duplicate tool strip.
- Public synthetic fallback remains illustrative and labelled DEMO; signed live access remains separately validated.

## Verified in local preview

- Public sample at 1280×800, 1440×900, 1920×1080 and 390×844: rendered, inspected, no document-level horizontal overflow or browser runtime errors.
- Sample page-outline navigation, page number entry, keyboard page navigation, evidence category filtering, PDF-to-evidence and evidence-to-PDF selection, Fit Width, Fit Page, persisted 110% zoom after hydration, inspector collapse.
- Signed admin/admin entry: Secure, HttpOnly, SameSite Strict cookie; guarded document list HTTP 200. Without signed cookie, document list HTTP 401.
- Existing ready synthetic-test PDF: actual page image loads, bbox selection opens exact detail. Existing segment-chart synthetic fixture: real source crop loads and matching bbox highlighted; Read chart control present but NOT invoked.
- Ask AI, Audit and Trends panels open in signed live workspace without runtime errors. No new QA, interpretation, Gateway call or upload made for this visual task; paid answer quality is not re-tested.
- Full Vitest suite: 102 passing tests. ESLint: zero errors, six pre-existing component-export warnings. Host automatic build log: build OK. Separate manual typecheck/build prohibited by workspace harness; fresh standalone typecheck and remote CI not independently observed.
- Source/service/proxy/session/budget/Windows files unchanged. No tunnel restart or configuration change.

## Publishing

Publication and official-site post-deploy checks are recorded in the task roadmap after deployment. Local screenshots alone are not proof of published behavior.