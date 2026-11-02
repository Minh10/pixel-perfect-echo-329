# Design refinement

- [x] Apply red-white identity throughout the existing app.
- [x] Redesign Overview using existing service data and real route links.
- [x] Improve document workspace toolbar and adjustable responsive panels.
- [x] Verify routes, workspace interactions, mobile layouts, tests and available lint/build signals.

Checks: 7 routing tests passed; redesigned files lint with no errors (one existing export warning); preview build reports OK; browser checks passed at 390, 768, 1440 and 1920px, including evidence selection, page keyboard navigation, zoom, highlights, panel controls and document filtering. Full-project lint retains 40 pre-existing formatting errors in untouched files and 6 export warnings. No manual build or typecheck run.

# Secure backend preparation

- [x] Enable Cloud in the existing project, retaining the login-free demo.
- [x] Prepare an authenticated, server-side FastAPI proxy without changing intake or processing architecture.
- [x] Document exact connection settings and unresolved access requirements in DEPLOYMENT.md.
- [x] Run proxy security and existing selection/routing tests; verify sample flow (18 tests passed, changed proxy/test files lint clean, preview build OK, sample opens and unconfigured proxy returns 503 with no browser errors).
- [ ] Activate private sign-in, native image/PDF secure session cookies and verify signup disabled (blocked: user clarified no login, demo only; authorized account not supplied; hosted signup configuration unverified).
- [ ] Connect and verify real published PDF processing (blocked: hosted FastAPI URL, shared token, authorized account).
