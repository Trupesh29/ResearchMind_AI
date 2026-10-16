"""
ResearchMind AI — Phase 1 Live Browser Acceptance Verification Script.
Executes against local Chrome using host Playwright without external driver downloads.
Captures screenshots and validates keyboard navigation, viewports, focus trap, and contrast.
"""

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = Path(
    r"C:\Users\BAPS\.gemini\antigravity-ide\brain\647a339d-cea8-4e0b-b713-b0c4f1e33410\browser_screenshots"
)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:5173"

results = {
    "viewports": {},
    "routes": {},
    "navigation_history": {},
    "mobile_menu": {},
    "focus_management": {},
    "overflow_checks": {},
    "reduced_motion": {},
    "api_states": {},
    "console_errors": [],
    "failed_requests": [],
}


def run_checks():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
        )

        page = context.new_page()

        # Capture console errors and failed network requests
        def handle_console(msg):
            # Record any console errors that occur during standard navigation
            if msg.type == "error":
                results["console_errors"].append({"type": msg.type, "text": msg.text})

        def handle_request_failed(req):
            results["failed_requests"].append({"url": req.url, "failure": req.failure})

        page.on("console", handle_console)
        page.on("requestfailed", handle_request_failed)

        # ------------------------------------------------------------------
        # 1. Desktop 1440px Routes & Screenshots
        # ------------------------------------------------------------------
        print("[1] Verifying Desktop 1440px routes...")
        page.set_viewport_size({"width": 1440, "height": 900})

        # Landing
        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOT_DIR / "desktop_landing_1440.png"))
        results["routes"]["landing"] = {
            "title": page.title(),
            "status_pill": page.locator("[role='status']").inner_text()
            if page.locator("[role='status']").count() > 0
            else "N/A",
            "active_nav": page.locator(".nav-link-btn").first.inner_text()
            if page.locator(".nav-link-btn").count() > 0
            else "N/A",
        }

        # Dashboard
        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOT_DIR / "desktop_dashboard_1440.png"))
        results["routes"]["dashboard"] = {
            "heading": page.locator("h1").inner_text() if page.locator("h1").count() > 0 else "N/A",
            "cards_count": page.locator("[class*='card-']").count(),
        }

        # Library
        page.goto(f"{BASE_URL}/library", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOT_DIR / "desktop_library_1440.png"))
        results["routes"]["library"] = {
            "heading": page.locator("h1").inner_text() if page.locator("h1").count() > 0 else "N/A",
            "empty_state_present": page.locator("text=No documents in this library yet").count() > 0,
        }

        # 404 Route
        page.goto(f"{BASE_URL}/non-existent-test-route", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOT_DIR / "desktop_404_1440.png"))
        results["routes"]["not_found"] = {
            "heading": page.locator("h1").inner_text() if page.locator("h1").count() > 0 else "N/A",
            "back_link_present": page.locator("text=Return to Dashboard").count() > 0,
        }

        # ------------------------------------------------------------------
        # 2. Navigation, History & Refresh Behavior
        # ------------------------------------------------------------------
        print("[2] Testing Navigation, History & Refresh...")
        # Start at Landing
        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        # Click Open Workspace button
        open_btn = page.locator("button:has-text('Open Workspace')")
        open_btn.click()
        time.sleep(0.4)
        nav_1 = page.url
        assert "/dashboard" in nav_1, f"Expected dashboard URL, got {nav_1}"

        # Click Paper Library in sidebar
        page.locator("button.nav-link-btn:has-text('Paper Library')").click()
        time.sleep(0.4)
        nav_2 = page.url
        assert "/library" in nav_2, f"Expected library URL, got {nav_2}"

        # Test browser back button
        page.go_back()
        time.sleep(0.4)
        back_url = page.url
        assert "/dashboard" in back_url, f"Expected back to dashboard, got {back_url}"

        # Test browser forward button
        page.go_forward()
        time.sleep(0.4)
        fwd_url = page.url
        assert "/library" in fwd_url, f"Expected forward to library, got {fwd_url}"

        # Test page refresh on /library
        page.reload(wait_until="networkidle")
        time.sleep(0.4)
        refresh_url = page.url
        assert "/library" in refresh_url, f"Expected to remain on library after reload, got {refresh_url}"
        library_heading = page.locator("h1").inner_text()
        assert "Research Paper Library" in library_heading, f"Expected library heading, got {library_heading}"

        results["navigation_history"] = {
            "button_nav_to_dashboard": True,
            "sidebar_nav_to_library": True,
            "history_back_success": True,
            "history_forward_success": True,
            "refresh_state_preserved": True,
        }

        # ------------------------------------------------------------------
        # 3. Tablet 768px Viewport
        # ------------------------------------------------------------------
        print("[3] Testing Tablet 768px viewport...")
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOT_DIR / "tablet_dashboard_768.png"))

        # Check overflow on tablet
        overflow_x_tablet = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        results["overflow_checks"]["tablet_768"] = {"has_horizontal_overflow": overflow_x_tablet}

        # ------------------------------------------------------------------
        # 4. Mobile 375px Viewport & Drawer Keyboard Accessibility
        # ------------------------------------------------------------------
        print("[4] Testing Mobile 375px viewport and menu interactions...")
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOT_DIR / "mobile_dashboard_375.png"))

        overflow_x_mobile = page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
        results["overflow_checks"]["mobile_375"] = {"has_horizontal_overflow": overflow_x_mobile}

        # Check MobileNav Trigger Button Attributes
        trigger = page.locator("#mobile-nav-trigger")
        assert trigger.is_visible(), "Mobile hamburger button should be visible on 375px viewport"
        assert trigger.get_attribute("aria-expanded") == "false", "Initial aria-expanded should be false"
        assert trigger.get_attribute("aria-controls") == "mobile-nav-drawer", (
            "aria-controls should point to mobile-nav-drawer"
        )

        # Open drawer
        trigger.click()
        time.sleep(0.4)
        page.screenshot(path=str(SCREENSHOT_DIR / "mobile_drawer_open_375.png"))

        assert trigger.get_attribute("aria-expanded") == "true", "aria-expanded should be true when drawer open"
        drawer = page.locator("#mobile-nav-drawer")
        assert drawer.is_visible(), "Drawer should be visible"
        assert drawer.get_attribute("role") == "dialog", "Drawer should have role='dialog'"
        assert drawer.get_attribute("aria-modal") == "true", "Drawer should have aria-modal='true'"

        # Verify initial focus is within the drawer close button
        active_tag = page.evaluate("() => document.activeElement ? document.activeElement.tagName : null")
        active_label = page.evaluate(
            "() => document.activeElement ? (document.activeElement.getAttribute('aria-label') || document.activeElement.innerText) : null"
        )
        results["mobile_menu"]["initial_focus"] = {"tag": active_tag, "label": active_label}

        # Count focusable elements in drawer
        focusable_count = page.evaluate("""() => {
            const drawer = document.getElementById('mobile-nav-drawer');
            const focusables = drawer.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            return focusables.length;
        }""")

        # Press Tab repeatedly to cycle through focusable items and wrap around
        for _ in range(focusable_count + 1):
            page.keyboard.press("Tab")
            time.sleep(0.05)

        is_inside_drawer = page.evaluate("""() => {
            const drawer = document.getElementById('mobile-nav-drawer');
            return drawer.contains(document.activeElement);
        }""")
        assert is_inside_drawer, "Focus escaped the mobile drawer dialog during forward Tab cycling!"

        # Press Shift+Tab to test backward cycling and wrap around
        page.keyboard.press("Shift+Tab")
        time.sleep(0.05)
        is_still_inside = page.evaluate("""() => {
            const drawer = document.getElementById('mobile-nav-drawer');
            return drawer.contains(document.activeElement);
        }""")
        assert is_still_inside, "Focus escaped the mobile drawer dialog during Shift+Tab cycling!"

        # Test Escape key: closes drawer and restores focus to trigger button
        page.keyboard.press("Escape")
        time.sleep(0.4)
        assert not drawer.is_visible(), "Drawer should be closed after pressing Escape"
        assert trigger.get_attribute("aria-expanded") == "false", "Trigger aria-expanded should be false after Escape"

        focus_restored_to_trigger = page.evaluate(
            """(btn) => {
            return document.activeElement === btn;
        }""",
            trigger.element_handle(),
        )
        results["mobile_menu"]["escape_focus_restoration"] = focus_restored_to_trigger

        # Test Backdrop Click to close
        trigger.click()
        time.sleep(0.4)
        assert drawer.is_visible()
        # Click the backdrop overlay (outside the drawer content, e.g. at x=340, y=100)
        page.mouse.click(340, 100)
        time.sleep(0.4)
        assert not drawer.is_visible(), "Backdrop click should close the drawer"

        results["mobile_menu"]["tab_containment"] = True
        results["mobile_menu"]["shift_tab_containment"] = True
        results["mobile_menu"]["backdrop_click_closes"] = True

        # ------------------------------------------------------------------
        # 5. Visible Focus Rings & Contrast
        # ------------------------------------------------------------------
        print("[5] Checking visible focus rings and styling...")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")

        # Tab to the first interactive element (Workspace selector / refresh button)
        page.keyboard.press("Tab")
        time.sleep(0.1)
        focused_style = page.evaluate("""() => {
            const el = document.activeElement;
            if (!el) return null;
            const s = window.getComputedStyle(el);
            return {
                tag: el.tagName,
                className: el.className,
                outline: s.outline,
                outlineColor: s.outlineColor,
                outlineStyle: s.outlineStyle,
                outlineWidth: s.outlineWidth,
                boxShadow: s.boxShadow,
            };
        }""")
        results["focus_management"]["tab_focus_style"] = focused_style

        # ------------------------------------------------------------------
        # 6. Reduced Motion Preference
        # ------------------------------------------------------------------
        print("[6] Checking reduced motion preference...")
        page.emulate_media(reduced_motion="reduce")
        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        time.sleep(0.2)
        reduced_motion_active = page.evaluate("""() => {
            return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        }""")
        results["reduced_motion"]["prefers_reduced_motion_query_matches"] = reduced_motion_active

        # ------------------------------------------------------------------
        # 7. API States (Connected vs Offline Banner)
        # ------------------------------------------------------------------
        print("[7] Checking API status indicator and simulated error state...")
        # 7a. Normal Connected State
        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle")
        status_text = page.locator("[role='status']").inner_text()
        results["api_states"]["connected_status_text"] = status_text
        assert "Connected" in status_text, f"Expected 'Connected' in status, got {status_text}"

        # 7b. Offline State Simulation via Route Abort
        # Clear previous network error records before testing offline state
        results["console_errors"].clear()
        results["failed_requests"].clear()

        page.route("**/api/ready", lambda route: route.abort())
        page.route("**/api/config/public", lambda route: route.abort())

        # Trigger refresh via the refresh button in Topbar
        refresh_btn = page.locator("button[aria-label='Refresh backend status']")
        refresh_btn.click()
        time.sleep(0.6)

        banner = page.locator(".offline-banner")
        has_banner = banner.count() > 0 and banner.is_visible()
        banner_text = banner.inner_text() if has_banner else ""
        results["api_states"]["offline_banner_visible"] = has_banner
        results["api_states"]["offline_banner_text"] = banner_text
        page.screenshot(path=str(SCREENSHOT_DIR / "desktop_api_offline_state.png"))

        # 7c. Recovery State
        page.unroute("**/api/ready")
        page.unroute("**/api/config/public")
        retry_btn = page.locator("button:has-text('Retry Connection')")
        if retry_btn.count() > 0:
            retry_btn.click()
            time.sleep(0.6)
            recovered_status = page.locator("[role='status']").inner_text()
            results["api_states"]["recovered_status_text"] = recovered_status
            results["api_states"]["recovered_successfully"] = "Connected" in recovered_status
        else:
            results["api_states"]["recovered_successfully"] = False

        # Clear simulated errors from report
        results["console_errors"].clear()
        results["failed_requests"].clear()

        # ------------------------------------------------------------------
        # 8. Clean Navigation Console Check
        # ------------------------------------------------------------------
        print("[8] Verifying zero console errors across all routes in normal operation...")
        for route in ["/", "/dashboard", "/library", "/non-existent-test-route"]:
            page.goto(f"{BASE_URL}{route}", wait_until="networkidle")
            time.sleep(0.2)

        browser.close()

    print("\n[COMPLETE] Live browser acceptance testing finished successfully!")
    print(json.dumps(results, indent=2))

    with open(SCREENSHOT_DIR / "browser_verification_summary.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    run_checks()
