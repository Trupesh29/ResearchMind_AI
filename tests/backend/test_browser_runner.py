"""
Regression tests for ResearchMind AI browser acceptance criteria evaluation.

Verifies that `evaluate_acceptance` strictly enforces all criteria:
- Responsive horizontal overflow (tablet and mobile)
- Mobile drawer accessibility (focus trapping, Escape focus restoration, background inertness)
- 404 recovery action
- Reduced motion suppression
- Contrast ratio thresholds
- API resilience & recovery
- Clean console & network operations (unexpected errors)
- Nonzero CLI exit on failure
"""

import copy
import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure scripts directory is on sys.path for importing runner functions
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_browser_verification import evaluate_acceptance, main  # noqa: E402


@pytest.fixture
def valid_browser_results() -> dict:
    """Returns a synthetic results dictionary where all criteria pass."""
    return {
        "overflow_checks": {
            "tablet_768": {"has_horizontal_overflow": False},
            "mobile_375": {"has_horizontal_overflow": False},
        },
        "routes": {
            "landing": {"title": "ResearchMind AI", "status_pill": "Backend Connected"},
            "dashboard": {"heading": "Workspace Dashboard", "cards_count": 3},
            "library": {"heading": "Research Paper Library", "empty_state_present": True},
            "not_found": {
                "heading": "Page Not Found",
                "h1_count": 1,
                "back_link_present": True,
                "recovery_action_navigates_to_dashboard": True,
            },
        },
        "navigation_history": {
            "button_nav_to_dashboard": True,
            "sidebar_nav_to_library": True,
            "history_back_success": True,
            "history_forward_success": True,
            "refresh_state_preserved": True,
        },
        "mobile_menu": {
            "initial_aria_expanded": "false",
            "open_aria_expanded": "true",
            "escape_aria_expanded": "false",
            "aria_controls": "mobile-nav-drawer",
            "dialog_role": "dialog",
            "aria_modal": "true",
            "initial_focus": {"tag": "BUTTON", "label": "Close navigation"},
            "initial_focus_correct": True,
            "tab_containment": True,
            "shift_tab_containment": True,
            "background_interaction_blocked": True,
            "drawer_closed_on_escape": True,
            "escape_focus_restoration": True,
            "backdrop_click_closes": True,
        },
        "reduced_motion": {
            "prefers_reduced_motion_query_matches": True,
            "animations_and_transitions_suppressed": True,
        },
        "contrast_checks": {
            "heading_on_canvas": {"ratio": 15.2, "threshold": 4.5, "passes": True},
            "body_text_on_canvas": {"ratio": 9.8, "threshold": 4.5, "passes": True},
            "status_pill_text": {"ratio": 5.4, "threshold": 4.5, "passes": True},
            "primary_button_text": {"ratio": 16.1, "threshold": 4.5, "passes": True},
        },
        "api_states": {
            "connected_status_text": "Backend Connected · SQLite Ready",
            "offline_banner_visible": True,
            "recovered_successfully": True,
        },
        "unexpected_console_errors": [],
        "unexpected_failed_requests": [],
        "simulated_offline_requests": [{"url": "http://127.0.0.1:8000/api/ready", "failure": "net::ERR_FAILED"}],
    }


def test_evaluate_acceptance_all_pass(valid_browser_results):
    passed, failures, criteria = evaluate_acceptance(valid_browser_results)
    assert passed is True
    assert len(failures) == 0
    assert all(status is True for status in criteria.values())


def test_evaluate_acceptance_fails_on_tablet_overflow(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["overflow_checks"]["tablet_768"]["has_horizontal_overflow"] = True

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["no_horizontal_overflow"] is False
    assert any("Tablet (768px) horizontal overflow" in f for f in failures)


def test_evaluate_acceptance_fails_on_mobile_overflow(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["overflow_checks"]["mobile_375"]["has_horizontal_overflow"] = True

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["no_horizontal_overflow"] is False
    assert any("Mobile (375px) horizontal overflow" in f for f in failures)


def test_evaluate_acceptance_fails_on_escape_focus_restoration_failure(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["escape_focus_restoration"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("Escape key did not restore focus" in f for f in failures)


def test_evaluate_acceptance_fails_on_tab_containment_failure(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["tab_containment"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("Tab focus containment failed" in f for f in failures)


def test_evaluate_acceptance_fails_on_background_interaction_not_blocked(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["background_interaction_blocked"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("did not block background interactions" in f for f in failures)


def test_evaluate_acceptance_fails_on_404_recovery_failure(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["routes"]["not_found"]["recovery_action_navigates_to_dashboard"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["routes_and_navigation"] is False
    assert any("404 recovery action" in f for f in failures)


def test_evaluate_acceptance_fails_on_unsuppressed_motion(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["reduced_motion"]["animations_and_transitions_suppressed"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["reduced_motion_suppressed"] is False
    assert any("Animations/transitions were not suppressed" in f for f in failures)


def test_evaluate_acceptance_fails_on_contrast_below_threshold(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["contrast_checks"]["body_text_on_canvas"] = {
        "ratio": 3.2,
        "threshold": 4.5,
        "passes": False,
    }

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["contrast_ratios"] is False
    assert any("Contrast failure for 'body_text_on_canvas'" in f for f in failures)


def test_evaluate_acceptance_fails_on_offline_banner_not_visible(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["api_states"]["offline_banner_visible"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["api_states_and_recovery"] is False
    assert any("did not display offline alert banner" in f for f in failures)


def test_evaluate_acceptance_fails_on_recovery_failure(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["api_states"]["recovered_successfully"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["api_states_and_recovery"] is False
    assert any("did not successfully recover" in f for f in failures)


def test_evaluate_acceptance_fails_on_unexpected_console_errors(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["unexpected_console_errors"] = [
        {"type": "error", "text": "Uncaught TypeError: Cannot read properties of undefined"}
    ]

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["clean_operation"] is False
    assert any("Unexpected console errors detected" in f for f in failures)


def test_evaluate_acceptance_fails_on_unexpected_failed_requests(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["unexpected_failed_requests"] = [
        {"url": "http://127.0.0.1:5173/assets/missing.js", "failure": "net::ERR_FILE_NOT_FOUND"}
    ]

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["clean_operation"] is False
    assert any("Unexpected failed network requests detected" in f for f in failures)


def test_evaluate_acceptance_fails_on_runner_exception(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["runner_exception"] = "TargetClosedError: Target page, context or browser has been closed"

    passed, failures, _ = evaluate_acceptance(results)
    assert passed is False
    assert any("Runner encountered an unhandled exception" in f for f in failures)


def test_cli_exits_nonzero_when_acceptance_fails(tmp_path):
    """Verifies that the main() CLI entry point exits with code 1 if acceptance fails."""
    summary_path = tmp_path / "summary.json"
    output_dir = tmp_path / "artifacts"

    failing_results = {
        "overflow_checks": {
            "tablet_768": {"has_horizontal_overflow": True},
            "mobile_375": {"has_horizontal_overflow": True},
        }
    }

    with patch("run_browser_verification.run_checks", return_value=(failing_results, False)):
        with patch(
            "sys.argv",
            ["run_browser_verification.py", "--output-dir", str(output_dir), "--summary-path", str(summary_path)],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


def test_cli_exits_zero_when_acceptance_passes(tmp_path, valid_browser_results):
    """Verifies that the main() CLI entry point exits with code 0 if acceptance passes."""
    summary_path = tmp_path / "summary.json"
    output_dir = tmp_path / "artifacts"

    with patch("run_browser_verification.run_checks", return_value=(valid_browser_results, True)):
        with patch(
            "sys.argv",
            ["run_browser_verification.py", "--output-dir", str(output_dir), "--summary-path", str(summary_path)],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


# ==============================================================================
# Modal Dialog & ARIA State Enforcement Tests
# ==============================================================================


def test_evaluate_acceptance_fails_on_drawer_closed_on_escape_false(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["drawer_closed_on_escape"] = False

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("did not close when Escape key was pressed" in f for f in failures)


def test_evaluate_acceptance_fails_on_dialog_role_not_dialog(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["dialog_role"] = "region"

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("Mobile drawer role is not 'dialog'" in f for f in failures)


def test_evaluate_acceptance_fails_on_aria_modal_not_true(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["aria_modal"] = "false"

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("Mobile drawer aria-modal is not 'true'" in f for f in failures)


def test_evaluate_acceptance_fails_on_trigger_initial_aria_expanded_invalid(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["initial_aria_expanded"] = "true"

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("trigger initial aria-expanded is not 'false'" in f for f in failures)


def test_evaluate_acceptance_fails_on_trigger_open_aria_expanded_invalid(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["open_aria_expanded"] = "false"

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("trigger open aria-expanded is not 'true'" in f for f in failures)


def test_evaluate_acceptance_fails_on_trigger_escape_aria_expanded_invalid(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["escape_aria_expanded"] = "true"

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("trigger post-escape aria-expanded is not 'false'" in f for f in failures)


def test_evaluate_acceptance_fails_on_trigger_aria_controls_invalid(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"]["aria_controls"] = "wrong-drawer-id"

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("trigger aria-controls is not 'mobile-nav-drawer'" in f for f in failures)


def test_evaluate_acceptance_fails_on_empty_mobile_menu(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"] = {}

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("Mobile drawer accessibility verification results missing or empty" in f for f in failures)


def test_evaluate_acceptance_fails_on_none_mobile_menu(valid_browser_results):
    results = copy.deepcopy(valid_browser_results)
    results["mobile_menu"] = None

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["mobile_drawer_accessibility"] is False
    assert any("Mobile drawer accessibility verification results missing or empty" in f for f in failures)


def test_committed_summary_fixture_rejects_modal_mutations():
    """Validates that mutating the committed docs/browser_verification_summary.json fixture fails."""
    summary_file = Path(__file__).resolve().parents[2] / "docs" / "browser_verification_summary.json"
    assert summary_file.exists(), "Committed summary fixture docs/browser_verification_summary.json must exist"

    with open(summary_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Clean un-mutated baseline passes
    passed, failures, _ = evaluate_acceptance(data)
    assert passed is True, f"Baseline committed summary failed evaluate_acceptance: {failures}"

    # Mutation 1: drawer_closed_on_escape = false
    mutated_1 = copy.deepcopy(data)
    mutated_1["mobile_menu"]["drawer_closed_on_escape"] = False
    p1, f1, c1 = evaluate_acceptance(mutated_1)
    assert p1 is False
    assert c1["mobile_drawer_accessibility"] is False

    # Mutation 2: dialog_role = "region"
    mutated_2 = copy.deepcopy(data)
    mutated_2["mobile_menu"]["dialog_role"] = "region"
    p2, f2, c2 = evaluate_acceptance(mutated_2)
    assert p2 is False
    assert c2["mobile_drawer_accessibility"] is False

    # Mutation 3: aria_modal = "false"
    mutated_3 = copy.deepcopy(data)
    mutated_3["mobile_menu"]["aria_modal"] = "false"
    p3, f3, c3 = evaluate_acceptance(mutated_3)
    assert p3 is False
    assert c3["mobile_drawer_accessibility"] is False


# ==============================================================================
# Process Lifecycle & Ownership Tests for run_browser_suite.ps1
# ==============================================================================

SUITE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_browser_suite.ps1"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_suite_rejects_occupied_port_without_touching_existing_server():
    """An existing listener on a required port must remain untouched, and the suite must exit 1."""
    occupied_port = find_free_port()
    other_port = find_free_port()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", occupied_port))
        server_sock.listen(5)

        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SUITE_SCRIPT),
            "-BackendPort",
            str(occupied_port),
            "-FrontendPort",
            str(other_port),
            "-TimeoutSeconds",
            "2",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        assert proc.returncode != 0
        assert f"Port {occupied_port} is already occupied" in (proc.stderr + proc.stdout)

        # Confirm the existing socket remains completely functional and untouched
        server_sock.settimeout(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
            client_sock.connect(("127.0.0.1", occupied_port))
            conn, _ = server_sock.accept()
            conn.close()


def test_suite_frontend_failure_cleans_up_backend():
    """If the frontend fails to launch, the newly launched backend must be cleanly terminated."""
    backend_port = find_free_port()
    frontend_port = find_free_port()

    # Launch a backend that sleeps for 60s, while frontend exits immediately with code 1
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SUITE_SCRIPT),
        "-BackendPort",
        str(backend_port),
        "-FrontendPort",
        str(frontend_port),
        "-BackendCommand",
        "powershell -NoProfile -Command Start-Sleep -Seconds 60",
        "-FrontendCommand",
        "powershell -NoProfile -Command exit 1",
        "-TimeoutSeconds",
        "3",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode != 0

    # Ensure backend port is NOT occupied and has been killed
    time.sleep(0.5)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Binding must succeed if no process is holding the port
        s.bind(("127.0.0.1", backend_port))


def test_suite_browser_failure_preserves_exit_code_and_cleans_up():
    """Runner failure exit code (e.g. 42) must be preserved, and owned processes cleaned up."""
    b_port = find_free_port()
    f_port = find_free_port()

    class ReadyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/ready":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ready"}')
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"OK")

        def log_message(self, format, *args):
            pass

    backend_server = HTTPServer(("127.0.0.1", b_port), ReadyHandler)
    frontend_server = HTTPServer(("127.0.0.1", f_port), ReadyHandler)

    t_b = threading.Thread(target=backend_server.serve_forever, daemon=True)
    t_f = threading.Thread(target=frontend_server.serve_forever, daemon=True)
    t_b.start()
    t_f.start()

    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SUITE_SCRIPT),
            "-Attach",
            "-BackendPort",
            str(b_port),
            "-FrontendPort",
            str(f_port),
            "-RunnerCommand",
            "powershell -NoProfile -Command exit 42",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 42
    finally:
        backend_server.shutdown()
        frontend_server.shutdown()


def test_suite_does_not_stop_unrelated_process():
    """The suite must never stop unrelated processes running on the machine."""
    unrelated_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert unrelated_proc.poll() is None

        occupied_port = find_free_port()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", occupied_port))
            s.listen(1)

            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SUITE_SCRIPT),
                "-BackendPort",
                str(occupied_port),
                "-FrontendPort",
                str(find_free_port()),
            ]
            subprocess.run(cmd, capture_output=True, text=True)

        # Unrelated process must still be running
        assert unrelated_proc.poll() is None
    finally:
        unrelated_proc.terminate()
        unrelated_proc.wait()
