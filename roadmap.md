# Existing FINAUDIT AI demonstration

- [x] Preserve existing red-white dashboard, one-step intake, public labelled sample, all routes and FastAPI/Docling interfaces.
- [x] Implement default-OFF temporary admin/admin server sessions without Cloud users; signed one-hour Secure/HttpOnly/SameSite cookie, durable revocation and same-origin guards.
- [x] Guard all existing frontend-used document APIs/assets with server-only upstream token and strict route/method/query/input validation.
- [x] Add durable atomic request/work/upload ceilings and 10 MiB / 30-page PDF inspection; fail closed if controls are unavailable.
- [x] Generate signing secret privately and document exact secrets, Windows commands, rotating tunnel URL, activation/publication and immediate shutdown.
- [x] Verify sample entry/exit/refresh/navigation and no-cookie 401 locally; tests/lint and automated typecheck/build checked. Published existing proxy returned 401; new session endpoint still 404 because unpublished.
- [x] Final activation preflight requested on 2026-11-02: confirm current main 968a527, named secrets and authenticated low-cost tunnel connectivity without revealing values.
- [x] Runtime URL is a valid HTTPS Quick Tunnel origin; health 200, document list with token 200, without token 401; stored signing secret signs/verifies and rejects tampering.
- [x] Repeat frontend tests (69 passed) and lint (0 errors, 6 existing warnings); inspect durable guard schema/grants and production no-cookie 401 / unrelated-path 404.
- [ ] Verify upstream job/model-call/token/concurrency and spending caps (Cursor/owner must supply Windows verification; POST ceilings are not dollar budgets).
- [ ] Verify real guard/session/proxy round trip and logout revocation; database runtime reservation probe could not assume service role, so fixture tests and schema/grants are not end-to-end proof.
- [ ] Activate and publish after controls pass (owner already authorized); FINAUDIT_TEMPORARY_DEMO_ENABLED absent/OFF, production demo-session endpoint 404. No VITE activation flag is used by current code.
- [ ] Verify published PDF upload/Ready/pages/images/citations/chart/discrepancy/trends workflow after preceding blockers; NOT RUN and nothing activated or published during preflight.
