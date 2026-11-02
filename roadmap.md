# Design refinement

- [x] Apply red-white identity throughout the existing app.
- [x] Redesign Overview using existing service data and real route links.
- [x] Improve document workspace toolbar and adjustable responsive panels.
- [x] Verify routes, workspace interactions, mobile layouts, tests and available lint/build signals.

Checks: 7 routing tests passed; redesigned files lint with no errors (one existing export warning); preview build reports OK; browser checks passed at 390, 768, 1440 and 1920px, including evidence selection, page keyboard navigation, zoom, highlights, panel controls and document filtering. Full-project lint retains 40 pre-existing formatting errors in untouched files and 6 export warnings. No manual build or typecheck run.

# Secure backend preparation

- [x] Remove public account UI and redirect legacy account pages to Overview; preserve demo notices and locked private requests. Verified public Overview/Documents/sample, legacy redirects and anonymous proxy 401 with no browser errors; 44 frontend tests pass, lint has zero errors/six existing warnings, automated compilation reports build OK. No standalone typecheck or production build was manually executed; hosted build status refers to an earlier commit.
- [x] Simplify administrator sign-in while preserving public exploration, persistent cookies and disabled live processing (38 tests passed, full lint zero errors/six existing warnings, browser verified public Overview/Documents/sample and default-password rejection).

- [x] Enable Cloud in the existing project, retaining the login-free demo.
- [x] Prepare an authenticated, server-side FastAPI proxy without changing intake or processing architecture.
- [x] Document exact connection settings and unresolved access requirements in DEPLOYMENT.md.
- [x] Run proxy security and existing selection/routing tests; verify sample flow (18 tests passed, changed proxy/test files lint clean, preview build OK, sample opens and unconfigured proxy returns 503 with no browser errors).
- [x] Implement single-account sign-in, password recovery, sign-out and authenticated report cookies; public sample unchanged.
- [ ] Implement and verify non-interactive owner-only access before live activation (blocked: hosting-edge/private-network access configuration is not supplied; existing cookie-based proxy remains locked).
- [x] Fix generated-file lint formatting failures without excluding semantic/security checks; full lint has zero errors and six existing warnings. Automated typecheck/build reports OK. Full frontend tests passed; production build was executed successfully by the investigation agent before final edits, not rerun after final edits.
- [ ] Connect and verify real published PDF processing (blocked: hosted FastAPI URL, shared token, verified non-interactive owner-only access).
