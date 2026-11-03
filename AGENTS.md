<!-- LOVABLE:BEGIN -->

> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

<!-- LOVABLE:END -->

## Architecture rules

- AI Gateway batch chart summaries use a separate signed-demo, same-origin server endpoint through FinAuditService; keep FastAPI interpretation/table verification unchanged because narrative summaries are not audited facts. Cache summaries and terminal gateway pauses in service-role-only storage; reserve existing request/work budgets plus a separate daily gateway ceiling before paid calls.

- All data access goes through `src/lib/api/service.ts` (`FinAuditService` interface + queryOptions); swap the demo implementation for a FastAPI HTTP client there — UI never imports demo data directly.
- Lovable Cloud provides secure server-side communication; FastAPI and Docling remain the document-processing backend because the accepted processing architecture must be preserved.
- All live browser requests use the same-origin document-service proxy; upstream credentials are read only inside server handlers. Default owner access remains fail-closed; an explicit server-only temporary demo switch permits a validated signed demo cookie with durable revocation and atomic budgets, never a Cloud identity.
- Owner sign-in uses server-side Cloud authentication and host-only Secure HttpOnly SameSite cookies for all report resources; the browser never receives the owner's session tokens from sign-in responses.
- Public sample routes remain ungated. Browser-only sample entry never authorizes requests; temporary live entry is separately validated server-side and remains publicly guessable, so activation requires verified upstream cost caps.
- Generated Cloud integration files retain semantic and security ESLint checks but not the app's Prettier rule because their generator controls formatting.
- Select live service only in browser effects after a server-verified enabled demo session; SSR always uses the public sample, preventing shared global live configuration from leaking between server requests.
- Temporary demo counters and revocation use service-role-only Cloud tables and atomic RPCs; never use in-memory rate limiting, and fail closed on guard failure.
- The global daily PDF allowance is defined in temporary-demo.ts and consumed by the proxy against UTC daily buckets; preserve historical counters when changing the allowance.
- Inspect bounded multipart PDF bytes with pdf-lib before forwarding temporary uploads; this enforces page limits without changing FastAPI/Docling processing.
- Any demo-sourced value must be visibly labelled DEMO; modules without a backend show an honest pending state, never simulated verification results.
- App shell (sidebar + header with breadcrumbs) lives in `__root.tsx`; nav items are defined once in `src/components/app/nav.ts`.
- Report tool navigation reuses the central nav labels and preserves the document search parameter; it is presentation-only and never triggers processing or selects service mode.
- The PDF workspace embeds shared question, chart-check and comparison panels beside the reader using URL tool state; legacy routes reuse those panels so features and secure service behavior stay consistent. Source links keep the current analysis tool while focusing the PDF evidence.
- Ask AI keeps the open PDF in request scope, derives suggested questions only from parsed facts with known periods, and leaves answer validation/abstention to FastAPI; this prevents unrelated report routing without fabricating answers.
- FastAPI QA accepts repeated totals only with stored same-table provenance and identical economic/period/unit/scope identity, separates calendar tokens from amounts, and retains verbatim citation checks; source edits never deploy to the owner's running Windows process automatically.

- Overview summaries derive from query-loaded service values; do not introduce a second data source for dashboard visuals.
- The library intelligence preview uses bounded sequential read-only service calls and conservatively compatible facts; missing/partial readings never imply zero discrepancies, and opening Overview never creates model work.
- Evaluation renders a curated projection of checked-in experiment artifacts, separating layout baselines from financial QA accuracy; refresh the projection from research results when experiments change.
- Document workspace uses a report-first two-pane resizable layout on desktop and bounded stacked views on mobile; thumbnails overlay the canvas, fit sizing follows the canvas via ResizeObserver, and presentation preferences never select service mode. Overview derives only from loaded document/page/evidence data; tool/page/evidence navigation stays URL-driven.
- Header and upload entry controls derive from the server-verified demo-session status; a tab-local sample entry never shows as live, so stale entries prompt re-activation instead.
- Decorative pointer feedback is browser-only, delegated and animation-frame throttled; global CSS owns motion tokens and reduced-motion handling so presentation never changes service selection or processing.
