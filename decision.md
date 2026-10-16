# ResearchMind AI decisions

Updated: 2026-10-16. Scope: Week 1 Phase 1 review and agent workflow.

## D001 - Phase boundaries

Retain the two-phase Week 1 plan. Phase 1 supplies project foundation and app shell; Phase 2 supplies workspace and PDF library lifecycle. The latest changes improve Phase 1 but do not yet satisfy all acceptance gates. Do not begin Phase 2 as part of the remaining correction task.

## D002 - Gravitas is agent guidance

Use `F:/dev/.agents/skills/gravitas/SKILL.md` and its `references/reconnaissance.md` for dependency-directed codebase understanding. Optimize agent context consumption through targeted searches, relevant diffs, direct callers, and focused tests. Do not implement Gravitas inside ResearchMind AI or alter product prompts, model context limits, chunk sizes, retrieval, or runtime token budgets for this purpose. No measured token savings are claimed.

Use compact planning, dependency context, impact-based verification, and no delegation by default. Skill-file availability is verified; slash-menu registration and Gravitas runtime/hooks are unverified. Apply the documented workflow manually when the runtime is unavailable, and label project checks as project checks, not Gravitas-owned validators.

## D003 - Schema authority and readiness

Alembic migrations are the executable schema authority. Readiness must verify the database revision against the expected migration head(s), not just table names. Preserve user data during upgrades. ORM defaults, constraints, and schema snapshots must agree with migrations; schema comparison must not silently ignore non-table differences.

## D004 - Consistent dependency injection

Application lifespan, readiness, public configuration, identity/bootstrap, and database dependencies must use the same effective settings/session ownership. Endpoints and dependency helpers must use FastAPI's recognized `Request` type annotation (`request: Request = None`) rather than generic `object`, ensuring FastAPI injects the actual `Request` context at runtime and omits accidental `request` query parameters from OpenAPI schemas. Tests must execute against the real dependency functions (`get_settings` and `get_db`) without masking them via `app.dependency_overrides`. Tests must isolate storage, database files, environment, and lifespan effects and restore injected state in teardown. Never rely only on the main database file's modification time as proof of isolation; SQLite WAL/SHM and storage writes matter too.

## D005 - Completion is evidence-based

Passing unit tests/builds does not establish browser accessibility, clean-install reproducibility, ML inference, or generator connectivity. Keep those statuses separate. No hosted provider or spending budget is approved by this review. Generator live connectivity remains unverified in this review (mock mode active). Browser acceptance is verified via live Google Chrome automation.

## Review evidence: current uncommitted working tree

- Backend: 43 passed, 37 warnings with full database and storage isolation (executed against real `get_settings` and `get_db` without dependency overrides).
- Dependency injection defect resolved: fixed `get_settings(request: Request = None)` and `get_db(request: Request = None)`. FastAPI now injects runtime `Request` instead of treating parameters as optional query inputs. OpenAPI schema confirmed to have zero `request` query parameters across all routes.
- Integration regressions: added `tests/backend/test_dependency_injection.py` verifying sentinel `app.state.settings` reaches `/api/config/public`, sentinel `app.state.session_factory` bypasses a poisoned global factory on `/api/ready`, `app.state.settings` controls readiness storage and identity checks, normal defaults work without overrides, and state/overrides are restored cleanly.
- Environment sensitivity resolved: `test_settings_defaults` isolated from caller environment via monkeypatch; explicit URL overrides tested separately.
- Frontend: 9 tests passed; lint (`eslint`), formatting (`prettier`), typecheck (`tsc`), and production build (`vite build`) passed with zero errors.
- Python: Ruff lint passed; format check reported 41 files already formatted.
- Readiness migration checks: deep revision comparison implemented covering `up_to_date`, `outdated`, `empty`, `absent`, and `unknown` states; pending migrations return HTTP 503 without mutating database.
- Schema comparison: `papers.status` aligned with `server_default="uploaded"`; Alembic regression check tests all differences (`compare_type=True`, `compare_server_default=True`) with 0 diffs.
- Populated database upgrade: verified upgrade from `0001` to `head` (`0002`) preserves existing records and enforces newly added check constraints on subsequent inserts.
- Browser Acceptance Gate CLOSED: Automated live browser verification executed via host Google Chrome (`C:\Program Files\Google\Chrome\Application\chrome.exe`) driven by Playwright (`F:\dev\apps\scrapling\Scripts\python.exe`). Verified routes (`/`, `/dashboard`, `/library`, `/non-existent-test-route`), viewports (1440x900 desktop, 768x1024 tablet, 375x812 mobile), drawer focus trap & Escape restoration, navigation & popstate history, offline banner & recovery, visible focus dual rings, reduced motion, and 0 console errors / failed assets.
- Responsive defect remediated: Fixed mobile horizontal overflow on 375px viewport (`scrollWidth` was 453px due to unconstrained topbar flex elements); adjusted `Topbar.tsx`, `StatusPill.tsx`, and `globals.css` with responsive hiding/truncation, reducing overflow to 0px. Fixed heading hierarchy on 404 page (`<h1>`).
- Generator status: offline development mode; live provider connectivity unverified (no external API key or spend approved).

## Status of corrections

1. [COMPLETED] Check actual migration head(s) in readiness and cover old/empty/unknown revisions.
2. [COMPLETED] Fix FastAPI dependency injection signatures (`request: Request = None`) in `get_settings` and `get_db`; remove masking `app.dependency_overrides` from test client; add 5 dedicated integration regressions covering app.state overrides, poisoned global factory bypass, OpenAPI parameters, readiness storage/identity checks, and default fallbacks.
3. [COMPLETED] Unify effective settings/session access and fully restore test overrides; isolate default-settings tests from caller environment; enforce full recursive storage directory snapshot guard.
4. [COMPLETED] Align ORM server defaults and compare all supported schema changes; explicitly test constraints and data-preserving upgrades.
5. [COMPLETED] Correct `docs/PHASE_1_VERIFICATION.md` and `README.md` to accurately report all verification gates.
6. [COMPLETED] Browser visual and interaction verification executed via native Google Chrome Playwright automation; mobile overflow defect fixed and verified; 8 screenshots captured; Browser Acceptance Gate is CLOSED.
