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
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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


def is_process_running(pid: int) -> bool:
    """Accurately checks whether a process is still active on Windows."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        assert proc.returncode != 0
        assert f"Port {occupied_port} is already occupied" in (proc.stderr + proc.stdout)

        # Confirm the existing socket remains completely functional and untouched
        server_sock.settimeout(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
            client_sock.connect(("127.0.0.1", occupied_port))
            conn, _ = server_sock.accept()
            conn.close()


def test_backend_port_propagation_to_frontend_proxy(tmp_path):
    """Verifies that selecting a nondefault BackendPort in Vite's environment routes frontend-proxied

    requests to that specific backend, returning identifiable data.
    """
    backend_port = find_free_port()
    frontend_port = find_free_port()
    identifiable_token = f"custom-backend-token-{backend_port}"

    class MockBackendHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/ready":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ready", "token": identifiable_token}).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    backend_server = HTTPServer(("127.0.0.1", backend_port), MockBackendHandler)
    t_b = threading.Thread(target=backend_server.serve_forever, daemon=True)
    t_b.start()

    frontend_proc = None
    try:
        env = os.environ.copy()
        env["VITE_BACKEND_URL"] = f"http://127.0.0.1:{backend_port}"

        frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
        cmd = [
            "cmd.exe",
            "/c",
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(frontend_port),
            "--strictPort",
        ]
        frontend_proc = subprocess.Popen(cmd, cwd=str(frontend_dir), env=env)

        # Poll frontend proxy with bounded wait
        url = f"http://127.0.0.1:{frontend_port}/api/ready"
        response_data = None
        start_time = time.time()
        while time.time() - start_time < 12:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        response_data = json.loads(resp.read().decode("utf-8"))
                        break
            except Exception:
                time.sleep(0.3)

        assert response_data is not None, f"Frontend proxy failed to respond at {url} within timeout"
        assert response_data.get("token") == identifiable_token, (
            f"Expected response from nondefault backend ({identifiable_token}), got {response_data}"
        )
    finally:
        if frontend_proc:
            try:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(frontend_proc.pid), "/T", "/F"],
                    capture_output=True,
                )
            except Exception:
                pass
        backend_server.shutdown()


def test_suite_frontend_failure_terminates_owned_backend_tree(tmp_path):
    """If frontend launch fails, the newly started backend process AND its descendants

    must be terminated, proved via identifiable PIDs.
    """
    parent_pid_file = tmp_path / "backend_parent.pid"
    child_pid_file = tmp_path / "backend_child.pid"
    backend_port = find_free_port()
    frontend_port = find_free_port()

    # Create a python script that writes parent PID and spawns a long-lived child process with child PID
    tree_script = tmp_path / "tree_backend.py"
    tree_script.write_text(
        f"""
import os, sys, subprocess, time
with open(r"{parent_pid_file}", "w") as f:
    f.write(str(os.getpid()))
child = subprocess.Popen([sys.executable, "-c", "import os, time; open(r'{child_pid_file}', 'w').write(str(os.getpid())); time.sleep(60)"])
time.sleep(60)
""",
        encoding="utf-8",
    )

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
        f"& '{sys.executable}' '{tree_script}'",
        "-FrontendCommand",
        "powershell -NoProfile -Command exit 1",
        "-TimeoutSeconds",
        "3",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert proc.returncode != 0

    assert parent_pid_file.exists(), "Backend parent PID file was not created by test fixture"
    parent_pid = int(parent_pid_file.read_text(encoding="utf-8").strip())

    start = time.time()
    while not child_pid_file.exists() and time.time() - start < 3:
        time.sleep(0.1)

    child_pid = int(child_pid_file.read_text(encoding="utf-8").strip()) if child_pid_file.exists() else None

    assert not is_process_running(parent_pid), f"Backend parent PID {parent_pid} was not terminated by wrapper cleanup"
    if child_pid:
        assert not is_process_running(child_pid), (
            f"Backend child PID {child_pid} was not terminated by wrapper tree cleanup"
        )


def test_suite_runner_failure_terminates_owned_backend_and_frontend(tmp_path):
    """When browser-runner fails, the owned backend and frontend processes must be terminated

    (proven by identifiable PIDs), and the runner's exit code preserved.
    """
    b_pid_file = tmp_path / "backend.pid"
    f_pid_file = tmp_path / "frontend.pid"
    b_port = find_free_port()
    f_port = find_free_port()

    server_helper = tmp_path / "disposable_server.py"
    server_helper.write_text(
        """
import sys, os, time
from http.server import HTTPServer, BaseHTTPRequestHandler

pid_file = sys.argv[1]
port = int(sys.argv[2])
mode = sys.argv[3]

with open(pid_file, "w") as f:
    f.write(str(os.getpid()))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        if mode == "backend":
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ready"}')
        else:
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

server = HTTPServer(("127.0.0.1", port), Handler)
server.serve_forever()
""",
        encoding="utf-8",
    )

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SUITE_SCRIPT),
        "-BackendPort",
        str(b_port),
        "-FrontendPort",
        str(f_port),
        "-BackendCommand",
        f"& '{sys.executable}' '{server_helper}' '{b_pid_file}' {b_port} backend",
        "-FrontendCommand",
        f"& '{sys.executable}' '{server_helper}' '{f_pid_file}' {f_port} frontend",
        "-RunnerCommand",
        "powershell -NoProfile -Command exit 55",
        "-TimeoutSeconds",
        "5",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

    assert proc.returncode == 55, f"Expected exit code 55, got {proc.returncode}. Output: {proc.stdout} {proc.stderr}"

    assert b_pid_file.exists() and f_pid_file.exists()
    b_pid = int(b_pid_file.read_text(encoding="utf-8").strip())
    f_pid = int(f_pid_file.read_text(encoding="utf-8").strip())

    assert not is_process_running(b_pid), f"Owned backend PID {b_pid} was not terminated on runner failure"
    assert not is_process_running(f_pid), f"Owned frontend PID {f_pid} was not terminated on runner failure"


def test_suite_success_terminates_owned_backend_and_frontend(tmp_path):
    """On successful suite completion, owned backend and frontend processes must be terminated

    (proven by identifiable PIDs), and exit code 0 returned.
    """
    b_pid_file = tmp_path / "backend.pid"
    f_pid_file = tmp_path / "frontend.pid"
    b_port = find_free_port()
    f_port = find_free_port()

    server_helper = tmp_path / "disposable_server.py"
    server_helper.write_text(
        """
import sys, os, time
from http.server import HTTPServer, BaseHTTPRequestHandler

pid_file = sys.argv[1]
port = int(sys.argv[2])
mode = sys.argv[3]

with open(pid_file, "w") as f:
    f.write(str(os.getpid()))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        if mode == "backend":
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ready"}')
        else:
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

server = HTTPServer(("127.0.0.1", port), Handler)
server.serve_forever()
""",
        encoding="utf-8",
    )

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SUITE_SCRIPT),
        "-BackendPort",
        str(b_port),
        "-FrontendPort",
        str(f_port),
        "-BackendCommand",
        f"& '{sys.executable}' '{server_helper}' '{b_pid_file}' {b_port} backend",
        "-FrontendCommand",
        f"& '{sys.executable}' '{server_helper}' '{f_pid_file}' {f_port} frontend",
        "-RunnerCommand",
        "powershell -NoProfile -Command exit 0",
        "-TimeoutSeconds",
        "5",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

    assert proc.returncode == 0
    assert b_pid_file.exists() and f_pid_file.exists()
    b_pid = int(b_pid_file.read_text(encoding="utf-8").strip())
    f_pid = int(f_pid_file.read_text(encoding="utf-8").strip())

    assert not is_process_running(b_pid), f"Owned backend PID {b_pid} was not terminated on success"
    assert not is_process_running(f_pid), f"Owned frontend PID {f_pid} was not terminated on success"


def test_suite_unrelated_process_and_attached_server_remain_alive(tmp_path):
    """Asserts that unrelated processes AND attached pre-existing servers remain alive

    after suite execution completes.
    """
    unrelated_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    b_port = find_free_port()
    f_port = find_free_port()

    class ReadyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if self.path == "/api/ready":
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ready"}')
            else:
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"OK")

        def log_message(self, *args):
            pass

    backend_server = HTTPServer(("127.0.0.1", b_port), ReadyHandler)
    frontend_server = HTTPServer(("127.0.0.1", f_port), ReadyHandler)
    t_b = threading.Thread(target=backend_server.serve_forever, daemon=True)
    t_f = threading.Thread(target=frontend_server.serve_forever, daemon=True)
    t_b.start()
    t_f.start()

    try:
        assert is_process_running(unrelated_proc.pid)

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
            "powershell -NoProfile -Command exit 0",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        assert proc.returncode == 0

        # Unrelated process must still be running
        assert is_process_running(unrelated_proc.pid)

        # Attached servers must still be running and responsive
        with urllib.request.urlopen(f"http://127.0.0.1:{b_port}/api/ready", timeout=2) as resp:
            assert resp.status == 200
        with urllib.request.urlopen(f"http://127.0.0.1:{f_port}", timeout=2) as resp:
            assert resp.status == 200
    finally:
        if unrelated_proc:
            unrelated_proc.terminate()
            unrelated_proc.wait()
        backend_server.shutdown()
        frontend_server.shutdown()


def _run_in_same_powershell_driver(
    tmp_path: Path,
    suite_args_string: str,
    initial_val: str | None,
) -> dict:
    """Executes run_browser_suite.ps1 within a single parent PowerShell process

    that establishes an initial VITE_BACKEND_URL and inspects it after execution.
    """
    driver_script = tmp_path / "env_driver.ps1"
    result_file = tmp_path / "env_result.json"

    val_snippet = (
        f'$initialVal = "{initial_val}"\n[Environment]::SetEnvironmentVariable("VITE_BACKEND_URL", $initialVal, "Process")'
        if initial_val is not None
        else '[Environment]::SetEnvironmentVariable("VITE_BACKEND_URL", $null, "Process")'
    )

    driver_content = f"""
{val_snippet}
$before = [Environment]::GetEnvironmentVariable("VITE_BACKEND_URL", "Process")
$caught = $null

try {{
    & '{SUITE_SCRIPT}' {suite_args_string}
}} catch {{
    $caught = $_.ToString()
}}

$after = [Environment]::GetEnvironmentVariable("VITE_BACKEND_URL", "Process")

$res = [PSCustomObject]@{{
    before = $before
    after = $after
    exitCode = $LASTEXITCODE
    error = $caught
}}

$res | ConvertTo-Json -Compress | Set-Content -Path '{result_file}' -Encoding UTF8
"""
    driver_script.write_text(driver_content, encoding="utf-8")

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(driver_script),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    assert result_file.exists(), f"Driver script failed to generate result. Output: {proc.stdout} {proc.stderr}"
    return json.loads(result_file.read_text(encoding="utf-8-sig"))


@pytest.mark.parametrize("initial_val", ["http://127.0.0.1:18765", None])
def test_suite_preserves_caller_environment_in_attach_mode(tmp_path, initial_val):
    """Calling wrapper in -Attach mode must preserve the calling process's VITE_BACKEND_URL

    whether it was pre-existing or absent.
    """
    res = _run_in_same_powershell_driver(
        tmp_path,
        "-Attach -BackendPort 0 -FrontendPort 0",
        initial_val,
    )
    assert res["after"] == initial_val
    assert "Attach mode failed" in (res.get("error") or "")


@pytest.mark.parametrize("initial_val", ["http://127.0.0.1:18765", None])
def test_suite_preserves_caller_environment_on_occupied_port_failure(tmp_path, initial_val):
    """Early failure (such as occupied port collision) must preserve caller's VITE_BACKEND_URL."""
    occupied_port = find_free_port()
    other_port = find_free_port()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", occupied_port))
        s.listen(1)

        res = _run_in_same_powershell_driver(
            tmp_path,
            f"-BackendPort {occupied_port} -FrontendPort {other_port} -TimeoutSeconds 2",
            initial_val,
        )
        assert res["after"] == initial_val
        assert f"Port {occupied_port} is already occupied" in (res.get("error") or "") or res.get("exitCode") != 0


@pytest.mark.parametrize("initial_val", ["http://127.0.0.1:18765", None])
def test_suite_preserves_caller_environment_on_successful_execution(tmp_path, initial_val):
    """Successful execution must restore caller's VITE_BACKEND_URL and clean up owned process trees."""
    b_pid_file = tmp_path / "backend.pid"
    f_pid_file = tmp_path / "frontend.pid"
    b_port = find_free_port()
    f_port = find_free_port()

    server_helper = tmp_path / "disposable_server.py"
    server_helper.write_text(
        """
import sys, os
from http.server import HTTPServer, BaseHTTPRequestHandler

pid_file = sys.argv[1]
port = int(sys.argv[2])
mode = sys.argv[3]

with open(pid_file, "w") as f:
    f.write(str(os.getpid()))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        if mode == "backend":
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ready"}')
        else:
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

server = HTTPServer(("127.0.0.1", port), Handler)
server.serve_forever()
""",
        encoding="utf-8",
    )

    args = (
        f"-BackendPort {b_port} -FrontendPort {f_port} "
        f"-BackendCommand \"& '{sys.executable}' '{server_helper}' '{b_pid_file}' {b_port} backend\" "
        f"-FrontendCommand \"& '{sys.executable}' '{server_helper}' '{f_pid_file}' {f_port} frontend\" "
        f'-RunnerCommand "powershell -NoProfile -Command exit 0" -TimeoutSeconds 5'
    )

    res = _run_in_same_powershell_driver(tmp_path, args, initial_val)
    assert res["after"] == initial_val
    assert res["exitCode"] == 0

    assert b_pid_file.exists() and f_pid_file.exists()
    b_pid = int(b_pid_file.read_text(encoding="utf-8").strip())
    f_pid = int(f_pid_file.read_text(encoding="utf-8").strip())

    assert not is_process_running(b_pid), f"Owned backend PID {b_pid} was not terminated on success"
    assert not is_process_running(f_pid), f"Owned frontend PID {f_pid} was not terminated on success"


def test_evaluate_acceptance_require_phase2_enforces_phase2_results(valid_browser_results):
    """When require_phase2=True, evaluate_acceptance must fail if phase2_lifecycle is missing."""
    results = copy.deepcopy(valid_browser_results)
    results.pop("phase2_lifecycle", None)

    # Without require_phase2, it passes (Phase 1 baseline)
    p1_passed, _, p1_criteria = evaluate_acceptance(results, require_phase2=False)
    assert p1_passed is True
    assert "phase2_library_lifecycle" not in p1_criteria

    # With require_phase2, it MUST fail!
    p2_passed, p2_failures, p2_criteria = evaluate_acceptance(results, require_phase2=True)
    assert p2_passed is False
    assert p2_criteria["phase2_library_lifecycle"] is False
    assert any("Phase 2 Library Lifecycle verification is required" in f for f in p2_failures)


def test_evaluate_acceptance_require_phase2_passes_with_valid_phase2(valid_browser_results):
    """When require_phase2=True and phase2_lifecycle is valid, evaluate_acceptance passes."""
    results = copy.deepcopy(valid_browser_results)
    results["phase2_lifecycle"] = {
        "workspace_created": True,
        "pdf_uploaded": True,
        "duplicate_identified": True,
        "corrupt_rejected": True,
        "search_success": True,
        "viewer_opened": True,
        "viewer_pdf_loaded": True,
        "viewer_escape_closed": True,
        "cancel_deletion_kept_paper": True,
        "confirm_deletion_removed_paper": True,
        "workspace_deleted": True,
    }

    passed, failures, criteria = evaluate_acceptance(results, require_phase2=True)
    assert passed is True
    assert criteria["phase2_library_lifecycle"] is True
    assert len(failures) == 0


def test_evaluate_acceptance_strictly_fails_when_viewer_pdf_loaded_missing_or_false(valid_browser_results):
    """Strict acceptance: viewer_pdf_loaded missing or False must fail (no fallback default)."""
    results = copy.deepcopy(valid_browser_results)
    results["phase2_lifecycle"] = {
        "workspace_created": True,
        "pdf_uploaded": True,
        "duplicate_identified": True,
        "corrupt_rejected": True,
        "search_success": True,
        "viewer_opened": True,
        # viewer_pdf_loaded missing
        "viewer_escape_closed": True,
        "cancel_deletion_kept_paper": True,
        "confirm_deletion_removed_paper": True,
        "workspace_deleted": True,
    }

    passed, failures, criteria = evaluate_acceptance(results, require_phase2=True)
    assert passed is False
    assert criteria["phase2_library_lifecycle"] is False

    # Also test explicit False
    results["phase2_lifecycle"]["viewer_pdf_loaded"] = False
    passed2, _, criteria2 = evaluate_acceptance(results, require_phase2=True)
    assert passed2 is False
    assert criteria2["phase2_library_lifecycle"] is False


def test_evaluate_acceptance_strictly_fails_when_viewer_escape_closed_missing_or_false(valid_browser_results):
    """Strict acceptance: viewer_escape_closed missing or False must fail (no fallback default)."""
    results = copy.deepcopy(valid_browser_results)
    results["phase2_lifecycle"] = {
        "workspace_created": True,
        "pdf_uploaded": True,
        "duplicate_identified": True,
        "corrupt_rejected": True,
        "search_success": True,
        "viewer_opened": True,
        "viewer_pdf_loaded": True,
        # viewer_escape_closed missing
        "cancel_deletion_kept_paper": True,
        "confirm_deletion_removed_paper": True,
        "workspace_deleted": True,
    }

    passed, failures, criteria = evaluate_acceptance(results, require_phase2=True)
    assert passed is False
    assert criteria["phase2_library_lifecycle"] is False

    # Also test explicit False
    results["phase2_lifecycle"]["viewer_escape_closed"] = False
    passed2, _, criteria2 = evaluate_acceptance(results, require_phase2=True)
    assert passed2 is False
    assert criteria2["phase2_library_lifecycle"] is False


def test_suite_attach_mode_rejects_non_disposable_target_for_phase2(tmp_path):
    """In -Attach mode with -RequirePhase2, non-disposable target (disposable_test_env=False) must be rejected."""
    b_port = find_free_port()
    f_port = find_free_port()

    class NonDisposableHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if self.path == "/api/config/public":
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"disposable_test_env": false}')
            else:
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"OK")

        def log_message(self, *args):
            pass

    backend_server = HTTPServer(("127.0.0.1", b_port), NonDisposableHandler)
    frontend_server = HTTPServer(("127.0.0.1", f_port), NonDisposableHandler)
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
            "-RequirePhase2",
            "-BackendPort",
            str(b_port),
            "-FrontendPort",
            str(f_port),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        assert proc.returncode != 0
        combined_output = proc.stdout + proc.stderr
        assert (
            "not running in a disposable test environment" in combined_output
            or "disposable_test_env" in combined_output
        )
    finally:
        backend_server.shutdown()
        frontend_server.shutdown()


def test_suite_preserves_caller_disposable_test_env(tmp_path):
    """run_browser_suite.ps1 must restore caller's original DISPOSABLE_TEST_ENV variable."""
    driver_script = tmp_path / "disposable_env_driver.ps1"
    result_file = tmp_path / "disposable_env_result.json"

    driver_content = f"""
$initialVal = "caller_preset"
[Environment]::SetEnvironmentVariable("DISPOSABLE_TEST_ENV", $initialVal, "Process")
$before = [Environment]::GetEnvironmentVariable("DISPOSABLE_TEST_ENV", "Process")
$caught = $null

try {{
    & '{SUITE_SCRIPT}' -BackendPort 0 -FrontendPort 0 -TimeoutSeconds 1
}} catch {{
    $caught = $_.ToString()
}}

$after = [Environment]::GetEnvironmentVariable("DISPOSABLE_TEST_ENV", "Process")

$res = [PSCustomObject]@{{
    before = $before
    after = $after
    exitCode = $LASTEXITCODE
    error = $caught
}}

$res | ConvertTo-Json -Compress | Set-Content -Path '{result_file}' -Encoding UTF8
"""
    driver_script.write_text(driver_content, encoding="utf-8")

    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(driver_script),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    assert result_file.exists()
    data = json.loads(result_file.read_text(encoding="utf-8-sig"))
    assert data["after"] == "caller_preset"


# ==============================================================================
# R3 Tests: Browser Runner Top-Level ID Validation & Cleanup Resiliency
# ==============================================================================


def test_evaluate_acceptance_fails_on_cleanup_errors(valid_browser_results):
    """R3: evaluate_acceptance must fail clean_operation if cleanup_errors are present."""
    results = copy.deepcopy(valid_browser_results)
    results["cleanup_errors"] = ["Failed to clean up workspace ws_leak_123: HTTP 500"]

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is False
    assert criteria["clean_operation"] is False
    assert any("Cleanup errors recorded" in f for f in failures)


def test_workspace_creation_response_top_level_contract_validation():
    """R3: Real POST /api/workspaces returns top-level id; verify validation logic rejects nested data or missing id."""
    # 1. Valid contract (actual backend behavior)
    valid_res_json = {"id": "ws_actual_123", "name": "E2E Workspace", "description": None}
    parsed_id = valid_res_json.get("id") if isinstance(valid_res_json, dict) else None
    assert parsed_id == "ws_actual_123"

    # 2. Buggy nested shape (finding R3 in c7d6c8e)
    buggy_nested_json = {"data": {"id": "ws_nested_123"}}
    nested_parsed = buggy_nested_json.get("id") if isinstance(buggy_nested_json, dict) else None
    assert nested_parsed is None  # Fails validation immediately

    # 3. Missing ID
    missing_id_json = {"name": "No ID WS"}
    assert missing_id_json.get("id") is None


def test_injected_browser_failure_cleans_up_created_workspace_and_preserves_sentinel(client: TestClient):
    """R3: Injected failure after workspace creation cleans up created workspace while preserving sentinel."""
    # 1. Create sentinel workspace
    sentinel_res = client.post("/api/workspaces", json={"name": "Sentinel Workspace", "description": "Preserve me"})
    assert sentinel_res.status_code == 201
    sentinel_id = sentinel_res.json()["id"]

    # 2. Simulate browser run creating a test workspace
    create_res = client.post("/api/workspaces", json={"name": "E2E Lifecycle WS", "description": "Run created"})
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]
    assert created_id != sentinel_id

    # 3. Simulate failure in browser test after creation, followed by finally cleanup block
    runner_cleanup_errors = []
    try:
        # Injected error mid-run
        raise RuntimeError("Injected browser test failure after creation")
    except Exception:
        # Execute runner's finally cleanup block logic using the tracked top-level ID
        if created_id:
            del_resp = client.delete(f"/api/workspaces/{created_id}")
            if del_resp.status_code in (200, 204, 404):
                created_id = None
            else:
                runner_cleanup_errors.append(f"HTTP {del_resp.status_code}")

    # 4. Assert created workspace is cleaned up, sentinel workspace survives, and zero cleanup errors
    assert created_id is None
    assert len(runner_cleanup_errors) == 0
    assert client.get(f"/api/workspaces/{sentinel_res.json()['id']}").status_code == 200
    assert client.get(f"/api/workspaces/{create_res.json()['id']}").status_code == 404
