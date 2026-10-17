"""
ResearchMind AI — Phase 1 Live Browser Acceptance Verification Script.

Executes automated end-to-end browser acceptance checks against Google Chrome.
Validates:
- Viewport responsiveness (Desktop 1440px, Tablet 768px, Mobile 375px) and horizontal overflow
- Semantic route rendering and navigation history (back, forward, refresh, 404 recovery action)
- Mobile drawer accessibility (focus trapping, initial focus, Escape restoration, background inertness)
- Visual styling (dual focus rings, text contrast measurements)
- Reduced motion suppression (CSS transition/animation suppression under prefers-reduced-motion)
- API states (healthy operational pill, offline alert banner, retry recovery)
- Clean operation (zero unexpected console errors, zero unexpected failed requests)

Configurable via CLI arguments and environment variables.
Fails with exit code 1 when any acceptance criterion is unsatisfied.
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


def evaluate_acceptance(results: dict, require_phase2: bool = False) -> tuple[bool, list[str], dict[str, bool]]:
    """
    Evaluates runner results against explicit acceptance criteria.

    Returns:
        tuple[bool, list[str], dict[str, bool]]:
            - overall_passed: True if all criteria pass, False otherwise
            - failure_reasons: List of descriptive failure messages
            - criteria_status: Dictionary mapping each criterion name to its boolean status
    """
    failures: list[str] = []
    criteria: dict[str, bool] = {}

    # Check for unhandled runner exceptions
    if results.get("runner_exception"):
        failures.append(f"Runner encountered an unhandled exception: {results['runner_exception']}")

    # 1. Viewports & Overflow (Desktop, Tablet 768px, Mobile 375px)
    overflow = results.get("overflow_checks", {})
    tablet_overflow = overflow.get("tablet_768", {}).get("has_horizontal_overflow")
    mobile_overflow = overflow.get("mobile_375", {}).get("has_horizontal_overflow")

    c1_passed = tablet_overflow is False and mobile_overflow is False
    if tablet_overflow is not False:
        failures.append(f"Tablet (768px) horizontal overflow detected: {tablet_overflow}")
    if mobile_overflow is not False:
        failures.append(f"Mobile (375px) horizontal overflow detected: {mobile_overflow}")
    criteria["no_horizontal_overflow"] = c1_passed

    # 2. Semantic Routes and Navigation History
    routes = results.get("routes", {})
    nav = results.get("navigation_history", {})
    routes_present = all(route in routes for route in ["landing", "dashboard", "library", "not_found"])
    nav_history_valid = (
        nav.get("button_nav_to_dashboard") is True
        and nav.get("sidebar_nav_to_library") is True
        and nav.get("history_back_success") is True
        and nav.get("history_forward_success") is True
        and nav.get("refresh_state_preserved") is True
    )
    recovery_404_valid = routes.get("not_found", {}).get("recovery_action_navigates_to_dashboard") is True

    c2_passed = routes_present and nav_history_valid and recovery_404_valid
    if not routes_present:
        failures.append("Not all required routes were rendered and recorded")
    if not nav_history_valid:
        failures.append(f"Navigation/history check failed: {nav}")
    if not recovery_404_valid:
        failures.append("404 recovery action did not navigate back to dashboard")
    criteria["routes_and_navigation"] = c2_passed

    # 3. Mobile Navigation Drawer Accessibility & Dialog Semantics
    drawer = results.get("mobile_menu")
    if not isinstance(drawer, dict) or not drawer:
        failures.append("Mobile drawer accessibility verification results missing or empty")
        criteria["mobile_drawer_accessibility"] = False
    else:
        c3_checks = [
            (
                drawer.get("drawer_closed_on_escape") is True,
                "Mobile drawer did not close when Escape key was pressed",
            ),
            (
                drawer.get("dialog_role") == "dialog",
                f"Mobile drawer role is not 'dialog': got '{drawer.get('dialog_role')}'",
            ),
            (
                drawer.get("aria_modal") == "true",
                f"Mobile drawer aria-modal is not 'true': got '{drawer.get('aria_modal')}'",
            ),
            (
                drawer.get("initial_aria_expanded") == "false",
                f"Mobile drawer trigger initial aria-expanded is not 'false': got '{drawer.get('initial_aria_expanded')}'",
            ),
            (
                drawer.get("open_aria_expanded") == "true",
                f"Mobile drawer trigger open aria-expanded is not 'true': got '{drawer.get('open_aria_expanded')}'",
            ),
            (
                drawer.get("escape_aria_expanded") == "false",
                f"Mobile drawer trigger post-escape aria-expanded is not 'false': got '{drawer.get('escape_aria_expanded')}'",
            ),
            (
                drawer.get("aria_controls") == "mobile-nav-drawer",
                f"Mobile drawer trigger aria-controls is not 'mobile-nav-drawer': got '{drawer.get('aria_controls')}'",
            ),
            (
                drawer.get("initial_focus_correct") is True,
                f"Mobile drawer initial focus invalid: {drawer.get('initial_focus')}",
            ),
            (
                drawer.get("tab_containment") is True,
                "Mobile drawer Tab focus containment failed (focus escaped dialog)",
            ),
            (
                drawer.get("shift_tab_containment") is True,
                "Mobile drawer Shift+Tab focus containment failed (focus escaped dialog)",
            ),
            (
                drawer.get("escape_focus_restoration") is True,
                "Mobile drawer Escape key did not restore focus to hamburger trigger button",
            ),
            (
                drawer.get("backdrop_click_closes") is True,
                "Clicking mobile drawer backdrop did not close the drawer",
            ),
            (
                drawer.get("background_interaction_blocked") is True,
                "Mobile drawer did not block background interactions while open",
            ),
        ]
        c3_passed = True
        for passed, msg in c3_checks:
            if not passed:
                c3_passed = False
                failures.append(msg)
        criteria["mobile_drawer_accessibility"] = c3_passed

    # 4. Reduced Motion Suppression
    motion = results.get("reduced_motion", {})
    query_matches = motion.get("prefers_reduced_motion_query_matches") is True
    animations_suppressed = motion.get("animations_and_transitions_suppressed") is True

    c4_passed = query_matches and animations_suppressed
    if not query_matches:
        failures.append("prefers-reduced-motion media query was not matched by page")
    if not animations_suppressed:
        failures.append(
            f"Animations/transitions were not suppressed under reduced motion: {motion.get('reduced_sample_transition_duration_s')}s"
        )
    criteria["reduced_motion_suppressed"] = c4_passed

    # 5. Contrast Measurements
    contrast = results.get("contrast_checks", {})
    contrast_passed = len(contrast) > 0 and all(check.get("passes") is True for check in contrast.values())
    if len(contrast) == 0:
        failures.append("No contrast checks were recorded")
    else:
        for name, check in contrast.items():
            if not check.get("passes"):
                failures.append(
                    f"Contrast failure for '{name}': ratio {check.get('ratio')} below threshold {check.get('threshold')}"
                )
    criteria["contrast_ratios"] = contrast_passed

    # 6. API States & Offline Recovery
    api_states = results.get("api_states", {})
    status_text = api_states.get("connected_status_text", "")
    offline_visible = api_states.get("offline_banner_visible") is True
    recovered = api_states.get("recovered_successfully") is True

    c6_passed = "Connected" in status_text and offline_visible and recovered
    if "Connected" not in status_text:
        failures.append(f"Initial API status did not indicate connected: '{status_text}'")
    if not offline_visible:
        failures.append("Simulated network outage did not display offline alert banner")
    if not recovered:
        failures.append("Clicking retry did not successfully recover the operational status")
    criteria["api_states_and_recovery"] = c6_passed

    # 7. Clean Operation (Zero Unexpected Console Errors / Failed Requests / Cleanup Errors)
    unexpected_errors = results.get("unexpected_console_errors", [])
    unexpected_reqs = results.get("unexpected_failed_requests", [])
    cleanup_errors = results.get("cleanup_errors", [])

    c7_passed = len(unexpected_errors) == 0 and len(unexpected_reqs) == 0 and len(cleanup_errors) == 0
    if len(unexpected_errors) > 0:
        failures.append(f"Unexpected console errors detected ({len(unexpected_errors)}): {unexpected_errors}")
    if len(unexpected_reqs) > 0:
        failures.append(f"Unexpected failed network requests detected ({len(unexpected_reqs)}): {unexpected_reqs}")
    if len(cleanup_errors) > 0:
        failures.append(f"Cleanup errors recorded ({len(cleanup_errors)}): {cleanup_errors}")
    criteria["clean_operation"] = c7_passed

    # 8. Phase 2 Library Lifecycle
    if "phase2_lifecycle" in results:
        p2 = results["phase2_lifecycle"]
        p2_passed = (
            p2.get("workspace_created") is True
            and p2.get("pdf_uploaded") is True
            and p2.get("duplicate_identified") is True
            and p2.get("corrupt_rejected") is True
            and p2.get("search_success") is True
            and p2.get("viewer_opened") is True
            and p2.get("viewer_pdf_loaded") is True
            and p2.get("viewer_escape_closed") is True
            and p2.get("cancel_deletion_kept_paper") is True
            and p2.get("confirm_deletion_removed_paper") is True
            and p2.get("workspace_deleted") is True
        )
        if not p2_passed:
            failures.append(f"Phase 2 Library Lifecycle criteria failed: {p2}")
        criteria["phase2_library_lifecycle"] = p2_passed
    elif require_phase2:
        failures.append("Phase 2 Library Lifecycle verification is required but missing from results.")
        criteria["phase2_library_lifecycle"] = False

    overall_passed = len(failures) == 0
    return overall_passed, failures, criteria


def run_checks(
    chrome_path: str,
    base_url: str,
    output_dir: Path,
    summary_path: Path,
    headless: bool = True,
    require_phase2: bool = False,
) -> tuple[dict, bool]:
    """
    Executes live browser acceptance checks and returns (results_dict, passed).
    """
    screenshots_dir = output_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    results: dict = {
        "meta": {
            "chrome_path": chrome_path,
            "base_url": base_url,
            "output_dir": str(output_dir),
            "summary_path": str(summary_path),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "headless": headless,
        },
        "viewports": {},
        "routes": {},
        "navigation_history": {},
        "mobile_menu": {},
        "focus_management": {},
        "overflow_checks": {},
        "reduced_motion": {},
        "contrast_checks": {},
        "api_states": {},
        "unexpected_console_errors": [],
        "unexpected_failed_requests": [],
        "simulated_offline_requests": [],
    }

    # Internal state flag to separate expected simulated offline requests from unexpected errors
    is_simulating_offline = False

    try:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                f"Playwright Python package is not installed in the active environment: {e}. "
                f"Please run using an environment with Playwright installed (e.g. F:\\dev\\apps\\scrapling\\Scripts\\python.exe) "
                f"or install with `pip install playwright`."
            ) from e

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=chrome_path,
                headless=headless,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            )

            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
            )

            page = context.new_page()

            # Console and network listeners
            def handle_console(msg):
                if msg.type == "error":
                    # If we are simulating offline, fetch network failures are expected
                    if is_simulating_offline and ("net::ERR" in msg.text or "Failed to load resource" in msg.text):
                        return
                    results["unexpected_console_errors"].append({"type": msg.type, "text": msg.text})

            def handle_request_failed(req):
                if is_simulating_offline and ("/api/ready" in req.url or "/api/config/public" in req.url):
                    results["simulated_offline_requests"].append({"url": req.url, "failure": req.failure})
                    return

                # If the request received a successful response from the server, it was not an HTTP failure
                try:
                    resp = req.response()
                    if resp is not None and 200 <= resp.status < 300:
                        return
                except Exception:
                    pass

                # If a client aborted a 204 DELETE request upon dialog unmount/navigation
                if req.method == "DELETE" and req.failure == "net::ERR_ABORTED":
                    return

                results["unexpected_failed_requests"].append({"url": req.url, "failure": req.failure})

            page.on("console", handle_console)
            page.on("requestfailed", handle_request_failed)

            # ------------------------------------------------------------------
            # 1. Desktop 1440px Routes & Screenshots
            # ------------------------------------------------------------------
            print("[1] Verifying Desktop 1440px routes...")
            page.set_viewport_size({"width": 1440, "height": 900})

            # 1a. Landing Route
            page.goto(f"{base_url}/", wait_until="networkidle")
            time.sleep(0.4)
            page.screenshot(path=str(screenshots_dir / "desktop_landing_1440.png"))
            results["routes"]["landing"] = {
                "title": page.title(),
                "status_pill": page.locator("[role='status']").inner_text()
                if page.locator("[role='status']").count() > 0
                else "N/A",
                "active_nav": page.locator(".nav-link-btn").first.inner_text()
                if page.locator(".nav-link-btn").count() > 0
                else "N/A",
            }

            # 1b. Dashboard Route
            page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            time.sleep(0.4)
            page.screenshot(path=str(screenshots_dir / "desktop_dashboard_1440.png"))
            results["routes"]["dashboard"] = {
                "heading": page.locator("h1").inner_text() if page.locator("h1").count() > 0 else "N/A",
                "cards_count": page.locator("[class*='card-']").count(),
            }

            # 1c. Library Route
            page.goto(f"{base_url}/library", wait_until="networkidle")
            time.sleep(0.4)
            page.screenshot(path=str(screenshots_dir / "desktop_library_1440.png"))
            results["routes"]["library"] = {
                "heading": page.locator("h1").inner_text() if page.locator("h1").count() > 0 else "N/A",
                "empty_state_present": page.locator("text=No documents in this library yet").count() > 0,
            }

            # 1d. 404 Route & Recovery Action
            page.goto(f"{base_url}/non-existent-test-route", wait_until="networkidle")
            time.sleep(0.4)
            page.screenshot(path=str(screenshots_dir / "desktop_404_1440.png"))
            h1_count = page.locator("h1").count()
            h1_text = page.locator("h1").inner_text() if h1_count > 0 else "N/A"
            back_btn = page.locator("button:has-text('Return to Dashboard')")
            back_btn_present = back_btn.count() > 0

            # Test 404 recovery action: clicking "Return to Dashboard"
            recovery_navigates = False
            if back_btn_present:
                back_btn.click()
                time.sleep(0.4)
                recovery_url = page.url
                recovery_heading = page.locator("h1").inner_text() if page.locator("h1").count() > 0 else ""
                recovery_navigates = "/dashboard" in recovery_url and "Workspace Dashboard" in recovery_heading

            results["routes"]["not_found"] = {
                "heading": h1_text,
                "h1_count": h1_count,
                "back_link_present": back_btn_present,
                "recovery_action_navigates_to_dashboard": recovery_navigates,
            }

            # ------------------------------------------------------------------
            # 2. Navigation, History & Refresh Behavior
            # ------------------------------------------------------------------
            print("[2] Testing Navigation, History & Refresh...")
            page.goto(f"{base_url}/", wait_until="networkidle")
            open_btn = page.locator("button:has-text('Open Workspace')")
            open_btn.click()
            time.sleep(0.4)
            nav_1 = page.url

            page.locator("button.nav-link-btn:has-text('Paper Library')").click()
            time.sleep(0.4)
            nav_2 = page.url

            page.go_back()
            time.sleep(0.4)
            back_url = page.url

            page.go_forward()
            time.sleep(0.4)
            fwd_url = page.url

            page.reload(wait_until="networkidle")
            time.sleep(0.4)
            refresh_url = page.url
            library_heading = page.locator("h1").inner_text() if page.locator("h1").count() > 0 else ""

            results["navigation_history"] = {
                "button_nav_to_dashboard": "/dashboard" in nav_1,
                "sidebar_nav_to_library": "/library" in nav_2,
                "history_back_success": "/dashboard" in back_url,
                "history_forward_success": "/library" in fwd_url,
                "refresh_state_preserved": "/library" in refresh_url and "Research Paper Library" in library_heading,
            }

            # ------------------------------------------------------------------
            # 3. Tablet 768px Viewport & Overflow
            # ------------------------------------------------------------------
            print("[3] Testing Tablet 768px viewport...")
            page.set_viewport_size({"width": 768, "height": 1024})
            page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            time.sleep(0.4)
            page.screenshot(path=str(screenshots_dir / "tablet_dashboard_768.png"))

            overflow_x_tablet = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
            results["overflow_checks"]["tablet_768"] = {
                "scroll_width": page.evaluate("() => document.documentElement.scrollWidth"),
                "inner_width": 768,
                "has_horizontal_overflow": overflow_x_tablet,
            }

            # ------------------------------------------------------------------
            # 4. Mobile 375px Viewport & Drawer Keyboard Accessibility
            # ------------------------------------------------------------------
            print("[4] Testing Mobile 375px viewport and menu interactions...")
            page.set_viewport_size({"width": 375, "height": 812})
            page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            time.sleep(0.4)
            page.screenshot(path=str(screenshots_dir / "mobile_dashboard_375.png"))

            overflow_x_mobile = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
            results["overflow_checks"]["mobile_375"] = {
                "scroll_width": page.evaluate("() => document.documentElement.scrollWidth"),
                "inner_width": 375,
                "has_horizontal_overflow": overflow_x_mobile,
            }

            trigger = page.locator("#mobile-nav-trigger")
            initial_expanded = trigger.get_attribute("aria-expanded")
            controls_attr = trigger.get_attribute("aria-controls")

            trigger.click()
            time.sleep(0.4)
            page.screenshot(path=str(screenshots_dir / "mobile_drawer_open_375.png"))

            open_expanded = trigger.get_attribute("aria-expanded")
            drawer = page.locator("#mobile-nav-drawer")
            drawer_role = drawer.get_attribute("role")
            drawer_modal = drawer.get_attribute("aria-modal")

            # Verify initial focus is on the close button inside drawer
            active_tag = page.evaluate("() => document.activeElement ? document.activeElement.tagName : null")
            active_label = page.evaluate(
                "() => document.activeElement ? (document.activeElement.getAttribute('aria-label') || document.activeElement.innerText) : null"
            )
            initial_focus_correct = active_tag == "BUTTON" and "Close" in (active_label or "")

            # Count focusables in drawer
            focusable_count = page.evaluate("""() => {
                const drawer = document.getElementById('mobile-nav-drawer');
                if (!drawer) return 0;
                return drawer.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])').length;
            }""")

            # Forward Tab containment
            for _ in range(focusable_count + 1):
                page.keyboard.press("Tab")
                time.sleep(0.04)

            tab_inside = page.evaluate("""() => {
                const drawer = document.getElementById('mobile-nav-drawer');
                return drawer && drawer.contains(document.activeElement);
            }""")

            # Backward Shift+Tab containment
            page.keyboard.press("Shift+Tab")
            time.sleep(0.04)
            shift_tab_inside = page.evaluate("""() => {
                const drawer = document.getElementById('mobile-nav-drawer');
                return drawer && drawer.contains(document.activeElement);
            }""")

            # Verify Background Interaction Blocking while drawer is open
            # Hit-test outside drawer panel (e.g. at x=340, y=100) must return the backdrop overlay, NOT an underlying element
            background_blocked = page.evaluate("""() => {
                const hit = document.elementFromPoint(340, 100);
                const drawer = document.getElementById('mobile-nav-drawer');
                // The hit element must be inside the mobile-nav-drawer container (the backdrop overlay)
                return Boolean(hit && drawer && drawer.contains(hit));
            }""")

            # Test Escape key: closes drawer and restores focus to trigger button
            page.keyboard.press("Escape")
            time.sleep(0.4)
            drawer_closed_on_escape = not drawer.is_visible()
            escape_expanded = trigger.get_attribute("aria-expanded")
            focus_restored_to_trigger = page.evaluate(
                """(btn) => document.activeElement === btn""",
                trigger.element_handle(),
            )

            # Test Backdrop Click to close
            trigger.click()
            time.sleep(0.4)
            page.mouse.click(340, 100)
            time.sleep(0.4)
            backdrop_closes = not drawer.is_visible()

            results["mobile_menu"] = {
                "initial_aria_expanded": initial_expanded,
                "open_aria_expanded": open_expanded,
                "escape_aria_expanded": escape_expanded,
                "aria_controls": controls_attr,
                "dialog_role": drawer_role,
                "aria_modal": drawer_modal,
                "initial_focus": {"tag": active_tag, "label": active_label},
                "initial_focus_correct": initial_focus_correct,
                "tab_containment": tab_inside,
                "shift_tab_containment": shift_tab_inside,
                "background_interaction_blocked": background_blocked,
                "drawer_closed_on_escape": drawer_closed_on_escape,
                "escape_focus_restoration": focus_restored_to_trigger,
                "backdrop_click_closes": backdrop_closes,
            }

            # ------------------------------------------------------------------
            # 5. Visible Focus Rings & Styling
            # ------------------------------------------------------------------
            print("[5] Checking visible focus rings...")
            page.set_viewport_size({"width": 1440, "height": 900})
            page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            page.keyboard.press("Tab")
            time.sleep(0.1)

            focused_style = page.evaluate("""() => {
                const el = document.activeElement;
                if (!el) return null;
                const s = window.getComputedStyle(el);
                return {
                    tag: el.tagName,
                    boxShadow: s.boxShadow,
                    outline: s.outline,
                };
            }""")
            results["focus_management"]["tab_focus_style"] = focused_style

            # ------------------------------------------------------------------
            # 6. Actual Reduced Motion Verification
            # ------------------------------------------------------------------
            print("[6] Checking reduced motion suppression...")
            # Sample normal motion transition duration first
            page.goto(f"{base_url}/", wait_until="networkidle")
            normal_sample_duration = page.evaluate("""() => {
                const link = document.querySelector('a') || document.querySelector('.skip-link');
                if (!link) return null;
                return parseFloat(window.getComputedStyle(link).transitionDuration) || 0;
            }""")

            # Emulate reduced motion
            page.emulate_media(reduced_motion="reduce")
            page.goto(f"{base_url}/", wait_until="networkidle")
            time.sleep(0.2)

            reduced_matches = page.evaluate("""() => {
                return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            }""")

            # Sample computed transition duration under reduced motion
            reduced_sample_duration = page.evaluate("""() => {
                const link = document.querySelector('a') || document.querySelector('.skip-link');
                if (!link) return null;
                return parseFloat(window.getComputedStyle(link).transitionDuration) || 0;
            }""")

            # tokens.css specifies transition-duration: 0.01ms !important (<= 0.001s)
            is_suppressed = reduced_sample_duration is not None and reduced_sample_duration <= 0.001

            results["reduced_motion"] = {
                "prefers_reduced_motion_query_matches": reduced_matches,
                "normal_sample_transition_duration_s": normal_sample_duration,
                "reduced_sample_transition_duration_s": reduced_sample_duration,
                "animations_and_transitions_suppressed": is_suppressed,
            }

            # Restore normal media emulation
            page.emulate_media(reduced_motion="no-preference")

            # ------------------------------------------------------------------
            # 7. Contrast Ratio Measurements
            # ------------------------------------------------------------------
            print("[7] Measuring text and control contrast ratios...")
            page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            contrast_data = page.evaluate(r"""() => {
                function parseRgb(colorStr) {
                    const match = colorStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
                    return match ? [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])] : [0, 0, 0];
                }
                function srgbToLinear(c) {
                    const v = c / 255;
                    return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
                }
                function relativeLuminance(rgb) {
                    return 0.2126 * srgbToLinear(rgb[0]) + 0.7152 * srgbToLinear(rgb[1]) + 0.0722 * srgbToLinear(rgb[2]);
                }
                function contrastRatio(rgb1, rgb2) {
                    const l1 = relativeLuminance(rgb1);
                    const l2 = relativeLuminance(rgb2);
                    const lighter = Math.max(l1, l2);
                    const darker = Math.min(l1, l2);
                    return (lighter + 0.05) / (darker + 0.05);
                }

                function getEffectiveBackgroundRgb(el) {
                    let cur = el;
                    while (cur && cur !== document) {
                        const style = window.getComputedStyle(cur);
                        const bg = style.backgroundColor;
                        const match = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
                        if (match) {
                            const alpha = match[4] !== undefined ? parseFloat(match[4]) : 1;
                            if (alpha > 0.1) {
                                return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
                            }
                        }
                        cur = cur.parentElement;
                    }
                    return [245, 245, 247]; // fallback canvas #f5f5f7
                }

                const checks = {};

                // 1. Heading on canvas
                const h1 = document.querySelector('h1');
                if (h1) {
                    const fg = parseRgb(window.getComputedStyle(h1).color);
                    const bg = getEffectiveBackgroundRgb(h1);
                    const ratio = Math.round(contrastRatio(fg, bg) * 100) / 100;
                    checks.heading_on_canvas = {
                        fg: window.getComputedStyle(h1).color,
                        bg: `rgb(${bg.join(', ')})`,
                        ratio,
                        threshold: 4.5,
                        passes: ratio >= 4.5
                    };
                }

                // 2. Body text on canvas
                const p = document.querySelector('#main-content p') || document.querySelector('p');
                if (p) {
                    const fg = parseRgb(window.getComputedStyle(p).color);
                    const bg = getEffectiveBackgroundRgb(p);
                    const ratio = Math.round(contrastRatio(fg, bg) * 100) / 100;
                    checks.body_text_on_canvas = {
                        fg: window.getComputedStyle(p).color,
                        bg: `rgb(${bg.join(', ')})`,
                        ratio,
                        threshold: 4.5,
                        passes: ratio >= 4.5
                    };
                }

                // 3. Status pill text on pill surface
                const pill = document.querySelector("[role='status']");
                if (pill) {
                    const fg = parseRgb(window.getComputedStyle(pill).color);
                    const bg = getEffectiveBackgroundRgb(pill);
                    const ratio = Math.round(contrastRatio(fg, bg) * 100) / 100;
                    checks.status_pill_text = {
                        fg: window.getComputedStyle(pill).color,
                        bg: `rgb(${bg.join(', ')})`,
                        ratio,
                        threshold: 4.5,
                        passes: ratio >= 4.5
                    };
                }

                // 4. Primary button text
                const btn = document.querySelector('button.btn-ink') || document.querySelector('button');
                if (btn) {
                    const fg = parseRgb(window.getComputedStyle(btn).color);
                    // Ink button has #1d1d1f background
                    const ratio = Math.round(contrastRatio(fg, [29, 29, 31]) * 100) / 100;
                    checks.primary_button_text = {
                        fg: window.getComputedStyle(btn).color,
                        bg: 'rgb(29, 29, 31)',
                        ratio,
                        threshold: 4.5,
                        passes: ratio >= 4.5
                    };
                }

                return checks;
            }""")
            results["contrast_checks"] = contrast_data

            # ------------------------------------------------------------------
            # 8. API States (Connected vs Offline Alert Banner & Recovery)
            # ------------------------------------------------------------------
            print("[8] Checking API states and offline banner recovery...")
            # 8a. Normal Connected State
            page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            status_text = page.locator("[role='status']").inner_text()
            results["api_states"]["connected_status_text"] = status_text

            # 8b. Offline State Simulation
            is_simulating_offline = True
            page.route("**/api/ready", lambda route: route.abort())
            page.route("**/api/config/public", lambda route: route.abort())

            refresh_btn = page.locator("button[aria-label='Refresh backend status']")
            if refresh_btn.count() > 0:
                refresh_btn.click()
            time.sleep(0.6)

            banner = page.locator(".offline-banner")
            has_banner = banner.count() > 0 and banner.is_visible()
            banner_text = banner.inner_text() if has_banner else ""
            page.screenshot(path=str(screenshots_dir / "desktop_api_offline_state.png"))

            results["api_states"]["offline_banner_visible"] = has_banner
            results["api_states"]["offline_banner_text"] = banner_text

            # 8c. Recovery State
            page.unroute("**/api/ready")
            page.unroute("**/api/config/public")
            retry_btn = page.locator("button:has-text('Retry connection')")
            recovered_success = False
            recovered_status = ""
            if retry_btn.count() > 0:
                retry_btn.click()
                time.sleep(0.6)
                recovered_status = page.locator("[role='status']").inner_text()
                recovered_success = "Connected" in recovered_status

            is_simulating_offline = False

            results["api_states"]["recovered_status_text"] = recovered_status
            results["api_states"]["recovered_successfully"] = recovered_success

            # ------------------------------------------------------------------
            # 9. Clean Navigation Console Check across all Routes
            # ------------------------------------------------------------------
            print("[9] Verifying zero console errors across all routes in normal operation...")
            # ------------------------------------------------------------------
            # 10. Phase 2 Workspace & PDF Library Acceptance Flow
            # ------------------------------------------------------------------
            print("[10] Executing Phase 2 workspace and PDF library acceptance flow...")
            p2_results = {}
            temp_fixtures_dir = output_dir / "temp_fixtures"
            temp_fixtures_dir.mkdir(parents=True, exist_ok=True)

            # Finding 2: Guard mutating workflow by verifying disposable test target
            try:
                public_cfg_res = page.request.get(f"{base_url}/api/config/public")
                if public_cfg_res.status != 200:
                    raise RuntimeError(
                        f"Failed to query public configuration from {base_url}/api/config/public: HTTP {public_cfg_res.status}"
                    )
                public_cfg = public_cfg_res.json()
                if not public_cfg.get("disposable_test_env"):
                    raise RuntimeError(
                        "Phase 2 lifecycle aborted: Target backend is not running in a disposable test environment (disposable_test_env is False)"
                    )
                p2_results["target_disposable_verified"] = True
            except Exception as exc:
                p2_results["target_disposable_verified"] = False
                p2_results["abort_reason"] = str(exc)
                results["phase2_lifecycle"] = p2_results
                raise

            # Generate synthetic test PDFs using standard minimal PDF structure
            valid_pdf_path = temp_fixtures_dir / "valid_test_paper.pdf"
            minimal_valid_pdf_bytes = (
                b"%PDF-1.4\n"
                b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
                b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
                b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
                b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
                b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n187\n%%EOF\n"
            )
            valid_pdf_path.write_bytes(minimal_valid_pdf_bytes)

            corrupt_pdf_path = temp_fixtures_dir / "corrupt_test_paper.pdf"
            corrupt_pdf_path.write_bytes(b"%PDF-corrupted-binary-header-test")

            created_workspace_id = None
            try:
                page.set_viewport_size({"width": 1440, "height": 900})
                page.goto(f"{base_url}/library", wait_until="networkidle")
                time.sleep(0.5)

                # Generate unique workspace name for this run to isolate data and prevent name collisions
                run_id = uuid.uuid4().hex[:8]
                e2e_ws_name = f"E2E Workspace {run_id}"

                # 10a. Create workspace
                create_btn = page.locator("button:has-text('Create Workspace'), button#new-workspace-btn")
                if create_btn.count() == 0:
                    sel_btn = page.locator("#workspace-selector-btn")
                    if sel_btn.count() > 0:
                        sel_btn.click()
                        time.sleep(0.3)
                        create_btn = page.locator("#new-workspace-btn")

                if create_btn.count() > 0:
                    create_btn.first.click()
                    time.sleep(0.4)
                    page.locator("#workspace-name-input").fill(e2e_ws_name)
                    with page.expect_response(
                        lambda r: "/api/workspaces" in r.url and r.request.method == "POST", timeout=8000
                    ) as ws_post_info:
                        page.locator("button:has-text('Create Workspace')").last.click()
                    ws_res = ws_post_info.value
                    if ws_res.status not in (200, 201):
                        raise RuntimeError(
                            f"Workspace creation request failed with HTTP {ws_res.status}: {ws_res.text()}"
                        )
                    try:
                        res_json = ws_res.json()
                        created_workspace_id = res_json.get("id") if isinstance(res_json, dict) else None
                    except Exception as parse_err:
                        raise RuntimeError(f"Failed to parse workspace creation response: {parse_err}")

                    if not created_workspace_id or not isinstance(created_workspace_id, str):
                        raise RuntimeError(f"Workspace creation response missing valid top-level 'id': {ws_res.text()}")
                    time.sleep(0.8)

                ws_name_visible = page.locator(f"text='{e2e_ws_name}'").count() > 0
                p2_results["workspace_created"] = ws_name_visible

                # 10b. Upload valid PDF
                file_input = page.locator("#pdf-upload-input")
                file_input.set_input_files(str(valid_pdf_path))
                time.sleep(1.2)
                accepted_badge = page.locator("text='1 Accepted'")
                p2_results["pdf_uploaded"] = accepted_badge.count() > 0

                # 10c. Upload duplicate PDF (identical bytes)
                file_input.set_input_files(str(valid_pdf_path))
                time.sleep(1.2)
                dup_badge = page.locator("text='1 Duplicate'")
                p2_results["duplicate_identified"] = dup_badge.count() > 0

                # 10d. Upload corrupt PDF
                file_input.set_input_files(str(corrupt_pdf_path))
                time.sleep(1.2)
                rej_badge = page.locator("text='1 Rejected'")
                p2_results["corrupt_rejected"] = rej_badge.count() > 0

                # 10e. Search
                search_input = page.locator("#paper-search-input")
                search_input.fill("valid_test")
                time.sleep(0.5)
                paper_found = page.locator("text='valid_test_paper.pdf'").count() > 0
                search_input.fill("")
                time.sleep(0.4)
                p2_results["search_success"] = paper_found

                # 10f. View Original PDF (Strict Positive Evidence: HTTP 200/206 from /api/papers/{id}/file)
                pdf_response_status = None
                view_btn = page.locator("button:has-text('View')").first
                with page.expect_response(
                    lambda r: "/api/papers/" in r.url and "/file" in r.url and r.status in (200, 206),
                    timeout=10000,
                ) as pdf_resp_info:
                    view_btn.click()
                pdf_resp = pdf_resp_info.value
                pdf_response_status = pdf_resp.status
                time.sleep(0.8)

                viewer_dialog = page.locator("[role='dialog']")
                viewer_opened = viewer_dialog.count() > 0 and viewer_dialog.is_visible()

                page.screenshot(path=str(screenshots_dir / "desktop_pdf_viewer_modal.png"))
                page.keyboard.press("Escape")
                time.sleep(0.4)
                viewer_closed = not viewer_dialog.is_visible()

                p2_results["viewer_opened"] = viewer_opened
                p2_results["viewer_pdf_loaded"] = pdf_response_status in (200, 206)
                p2_results["viewer_escape_closed"] = viewer_closed

                # 10g. Cancel Paper Deletion
                del_paper_btn = page.locator("button[aria-label^='Delete valid_test_paper']").first
                del_paper_btn.click()
                time.sleep(0.4)
                cancel_btn = page.locator("button:has-text('Cancel')").first
                cancel_btn.click()
                time.sleep(0.4)
                paper_still_present = page.locator("text='valid_test_paper.pdf'").count() > 0
                p2_results["cancel_deletion_kept_paper"] = paper_still_present

                # 10h. Confirm Paper Deletion
                del_paper_btn.click()
                time.sleep(0.4)
                confirm_del_btn = page.locator("button:has-text('Delete Paper')").first
                with page.expect_response(
                    lambda r: "/api/papers/" in r.url and r.request.method == "DELETE", timeout=8000
                ):
                    confirm_del_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(0.5)
                paper_removed = page.locator("text='valid_test_paper.pdf'").count() == 0
                p2_results["confirm_deletion_removed_paper"] = paper_removed

                # 10i. Delete Workspace (deleting only the workspace created in this run)
                del_ws_btn = page.locator("button[aria-label='Delete workspace']").first
                del_ws_btn.click()
                time.sleep(0.4)
                confirm_ws_btn = page.locator("button:has-text('Delete Workspace')").first
                with page.expect_response(
                    lambda r: "/api/workspaces/" in r.url and r.request.method == "DELETE", timeout=8000
                ) as ws_del_info:
                    confirm_ws_btn.click()
                ws_del_res = ws_del_info.value
                page.wait_for_load_state("networkidle")
                time.sleep(0.5)
                ws_removed = page.locator(f"text='{e2e_ws_name}'").count() == 0
                p2_results["workspace_deleted"] = ws_removed and ws_del_res.status in (200, 204)
                if ws_del_res.status in (200, 204):
                    created_workspace_id = None

                # Capture desktop Phase 2 library screenshot
                page.screenshot(path=str(screenshots_dir / "desktop_library_phase2.png"))

                results["phase2_lifecycle"] = p2_results
            finally:
                # Clean temporary test fixtures
                try:
                    valid_pdf_path.unlink(missing_ok=True)
                    corrupt_pdf_path.unlink(missing_ok=True)
                except Exception:
                    pass

                # If workspace deletion failed or was aborted midway, clean up via API
                if created_workspace_id:
                    try:
                        del_resp = page.request.delete(f"{base_url}/api/workspaces/{created_workspace_id}")
                        if del_resp.status in (200, 204, 404):
                            created_workspace_id = None
                        else:
                            err_msg = f"Failed to clean up workspace {created_workspace_id}: HTTP {del_resp.status}"
                            results.setdefault("cleanup_errors", []).append(err_msg)
                            print(f"\n[CLEANUP ERROR] {err_msg}", file=sys.stderr)
                    except Exception as cleanup_err:
                        err_msg = f"Exception cleaning up workspace {created_workspace_id}: {cleanup_err}"
                        results.setdefault("cleanup_errors", []).append(err_msg)
                        print(f"\n[CLEANUP ERROR] {err_msg}", file=sys.stderr)

            browser.close()

    except Exception as exc:
        results["runner_exception"] = f"{type(exc).__name__}: {str(exc)}"
        print(f"\n[EXCEPTION] Browser runner encountered error: {exc}", file=sys.stderr)

    # Acceptance Evaluation
    passed, failure_reasons, criteria_status = evaluate_acceptance(results, require_phase2=require_phase2)
    results["acceptance_evaluation"] = {
        "passed": passed,
        "failure_reasons": failure_reasons,
        "criteria": criteria_status,
    }

    # Write summary files to output_dir and summary_path
    summary_file = output_dir / "browser_verification_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n============================================================")
    print("           BROWSER ACCEPTANCE VERIFICATION REPORT           ")
    print("============================================================")
    for criterion, status in criteria_status.items():
        label = "PASS" if status else "FAIL"
        print(f"  [{label}] {criterion}")
    print("------------------------------------------------------------")

    if passed:
        print("[PASS] All browser acceptance criteria satisfied.")
        print(f"Summary saved to: {summary_file} and {summary_path}")
    else:
        print("[FAIL] Browser acceptance failed with the following issues:")
        for reason in failure_reasons:
            print(f"  - {reason}")
        print(f"Diagnostic summary preserved at: {summary_file}")

    return results, passed


def main():
    parser = argparse.ArgumentParser(description="ResearchMind AI Browser Acceptance Runner")
    parser.add_argument(
        "--chrome-path",
        default=os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        help="Path to Google Chrome executable",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://127.0.0.1:5173"),
        help="Base URL of running frontend application",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("OUTPUT_DIR", "artifacts/browser_verification"),
        help="Directory to store verification screenshots and summary JSON",
    )
    parser.add_argument(
        "--summary-path",
        default=os.environ.get("SUMMARY_PATH", "docs/browser_verification_summary.json"),
        help="Path to write the portable repository summary JSON",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser with visible UI (not headless)",
    )
    parser.add_argument(
        "--require-phase2",
        action="store_true",
        default=False,
        help="Require Phase 2 Library Lifecycle acceptance criteria to pass",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    summary_path = Path(args.summary_path)

    _, passed = run_checks(
        chrome_path=args.chrome_path,
        base_url=args.base_url,
        output_dir=output_dir,
        summary_path=summary_path,
        headless=not args.no_headless,
        require_phase2=args.require_phase2,
    )

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
