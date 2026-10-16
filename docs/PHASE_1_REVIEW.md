# Phase 1 review - 2026-10-16

Scope: current working-tree corrections since `51e3071`, including the new browser runner. A local checkpoint commit is authorized; no push is authorized.

## Findings

### P2 - Browser runner records failures without enforcing acceptance

`scripts/run_browser_verification.py` stores tablet/mobile overflow, Escape focus restoration, offline-banner presence, API recovery, console errors, and failed requests without asserting their acceptance values. It unconditionally prints a success message if execution reaches the end. A run with `recovered_successfully: false` or `has_horizontal_overflow: true` can therefore exit successfully. Require a final explicit acceptance evaluation and a nonzero exit code on failure, while retaining diagnostic JSON/screenshots. Add regression checks that inject failing result values.

### P2 - Accessibility claims exceed what the runner measures

The reduced-motion check only confirms the emulated media query, not actual suppression of animations/transitions. No contrast-ratio measurement is implemented. Background interaction blocking and 404 recovery clicks are described in the verification report but are not exercised by this runner. The broad WCAG wording and complete acceptance claim need narrower evidence or additional actual checks. This does not invalidate the recorded successful navigation and zero-overflow observations.

## Reproducibility improvement

The runner hardcodes a user-specific Antigravity session output path, Chrome executable, and localhost URL. Expose these as arguments or environment configuration, document the Playwright dependency/setup, and keep portable evidence summaries in the repository with generated screenshots outside version control. Retain expected simulated network failures separately instead of clearing earlier diagnostic collections.

## Evidence observed in this review

- Backend: 43 tests passed, 37 warnings. Real dependency-injection regressions remain present.
- Ruff lint passed; formatting check reported 26 files already formatted.
- Frontend: 9 tests passed; lint, format check, TypeScript check, and production build passed. JSDOM emitted scrollTo-not-implemented diagnostics. No application behavior was changed by this review.
- Existing browser summary was read from the documented Antigravity artifact directory. It records no tablet/mobile overflow, successful focus containment/restoration, successful offline recovery, and no errors in its final normal-navigation phase. This is previous-run evidence, not a new browser run.
- The frontend development server was not listening at 127.0.0.1:5173 during this review. No new live browser run or fresh ML/provider connectivity check was performed.
- Current user instruction: commit reviewed work locally; do not push. A checkpoint commit does not close unresolved acceptance findings.

## Follow-up review of commit 19397ec

The original unconditional-success issue is substantially addressed: explicit acceptance evaluation, nonzero failure exits, configurable runner paths, preserved diagnostics, and a portable result summary are now present. Contrast sampling and reduced-motion sampling were added. The earlier findings above remain historical context, not a claim that these improvements are absent.

### P1 - Wrapper does not reliably own the processes it verifies or stops

`scripts/run_browser_suite.ps1` starts both processes before entering its cleanup try/finally. If frontend launch fails, the already-started backend is not cleaned up. It polls fixed URLs without confirming the newly spawned processes survived or own those ports; existing servers can satisfy the checks after new launches fail, and Vite can fall back to a different port. Cleanup stops the npm command shell rather than reliably owning its Node descendants, then uses an executable-path-wide process sweep. That sweep can terminate a pre-existing project Uvicorn server while missing the newly started Node process installed outside the project directory.

Use explicit ownership of launched process trees, protect all launch paths with cleanup, and either reject occupied ports or provide an explicit attach mode that never stops existing servers. Use strict port binding and check launched-process exits. Only terminate processes created by this invocation. Test startup failure, occupied ports, normal completion, and browser-runner failure with harmless disposable process fixtures. This finding is based on code inspection; the unsafe wrapper was not executed during review.

### P2 - Recorded modal failures still pass the evaluator

Using the committed `docs/browser_verification_summary.json` as the baseline, separately setting `mobile_menu.drawer_closed_on_escape` to false, `dialog_role` to `region`, or `aria_modal` to `false` still makes `evaluate_acceptance()` return true. These fields are collected by the browser runner but omitted from the required modal criteria. Enforce the recorded Escape-close and dialog/ARIA contracts, including required trigger state transitions, with false/missing-value regression cases. The current passing fixture is not evidence that these failure paths are correctly rejected.

### Fresh checks

- 59 backend/runner tests passed, with 37 dependency deprecation warnings.
- Ruff lint passed; 27 files already formatted.
- Nine frontend tests passed; frontend lint, formatting, TypeScript, and production build passed. JSDOM emitted scrollTo-not-implemented diagnostics.
- Acceptance mutation checks reproduced the three false-pass cases above.
- No live browser suite, ML inference, provider call, or remote push was performed in this follow-up review.

## Resolution of Follow-up Review Findings (Post-19397ec)

### P1 - Wrapper process ownership and port lifecycle [RESOLVED]
- **Remediation in `scripts/run_browser_suite.ps1`:**
  - Entire launch and execution lifecycle is wrapped in a `try ... finally` block from the start.
  - Added strict port collision guard (`Test-PortListening`): if ports 8000 or 5173 are occupied, the suite terminates immediately with an informative error rather than colliding with or killing pre-existing servers.
  - Added explicit `-Attach` mode switch: connects to pre-existing running servers without terminating them upon suite completion.
  - Configured strict port binding in `frontend/vite.config.ts` (`server.strictPort = true`) and CLI `--strictPort` argument.
  - Implemented PID tree tracking and termination via `Stop-OwnedProcessTree`: uses Windows `taskkill.exe /PID $pid /T /F` followed by CIM child process inspection to terminate only the launched process trees (`$backendProc.Id` and `$frontendProc.Id`).
  - Broad executable-name and project path process sweeps (`Get-Process -Name node, uvicorn ...`) were completely removed.
  - Preserved the test runner's failure exit code in `$exitCode` without modification during cleanup.
  - Verified with 4 disposable lifecycle regressions in `tests/backend/test_browser_runner.py` testing port collision, frontend launch failure backend cleanup, runner exit code preservation, and immunity of unrelated processes.

### P2 - Modal acceptance evaluation completeness [RESOLVED]
- **Remediation in `scripts/run_browser_verification.py`:**
  - Enforced all 13 mobile modal criteria in `evaluate_acceptance()`:
    - Escape closure: `drawer_closed_on_escape == True`.
    - Dialog semantics: `dialog_role == "dialog"`, `aria_modal == "true"`.
    - Trigger state transitions: `initial_aria_expanded == "false"`, `open_aria_expanded == "true"`, `escape_aria_expanded == "false"`, `aria_controls == "mobile-nav-drawer"`.
    - Initial focus on close button, Tab and Shift+Tab containment, Escape focus restoration, backdrop click closure, and background interaction blocking.
    - Missing or empty `mobile_menu` dictionary explicitly fails instead of passing silently.
  - Added 10 regression tests in `tests/backend/test_browser_runner.py` covering every modal failure path and testing direct mutations of `docs/browser_verification_summary.json`.

### Verification Status After Remediation
- Backend tests: 73 passed (43 core foundation + 30 runner criteria & lifecycle tests), 0 failures.
- Frontend tests: 9 passed, 0 failures.
- Live Google Chrome run: All 7 acceptance criteria verified passing under host Chrome; summary saved to `docs/browser_verification_summary.json`.
- Zero ports or orphaned processes retained post-run.
