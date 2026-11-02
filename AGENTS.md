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

- All data access goes through `src/lib/api/service.ts` (`FinAuditService` interface + queryOptions); swap the demo implementation for a FastAPI HTTP client there — UI never imports demo data directly.
- Lovable Cloud provides secure server-side communication; FastAPI and Docling remain the document-processing backend because the accepted processing architecture must be preserved.
- All live browser requests use the same-origin document-service proxy; upstream credentials are read only inside server handlers, and private access fails closed without an explicitly authorized account.
- Owner sign-in uses server-side Cloud authentication and host-only Secure HttpOnly SameSite cookies for all report resources; the browser never receives the owner's session tokens from sign-in responses.
- Administrator password validation is shared between the server login and its tests; public demo routes remain ungated and sign-out returns to public Overview.
- Generated Cloud integration files retain semantic and security ESLint checks but not the app's Prettier rule because their generator controls formatting.
- Keep proxy mode opt-in and the login-free sample demo as default until service configuration and private access are complete; this prevents an unavailable backend from blocking the accepted preview.
- Any demo-sourced value must be visibly labelled DEMO; modules without a backend show an honest pending state, never simulated verification results.
- App shell (sidebar + header with breadcrumbs) lives in `__root.tsx`; nav items are defined once in `src/components/app/nav.ts`.

- Overview summaries derive from query-loaded service values; do not introduce a second data source for dashboard visuals.
- Document workspace uses the installed resizable panel primitives on desktop and stacked, bounded views on smaller screens, preserving URL-driven page navigation.
