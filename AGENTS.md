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
- No database / Lovable Cloud and no live LLM calls until an explicit architecture decision is made; the backend will be FastAPI.
- Any demo-sourced value must be visibly labelled DEMO; modules without a backend show an honest pending state, never simulated verification results.
- App shell (sidebar + header with breadcrumbs) lives in `__root.tsx`; nav items are defined once in `src/components/app/nav.ts`.
