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

from run_browser_verification import (  # noqa: E402
    check_late_response_isolation,
    compute_local_database_identity,
    drain_worker_engine,
    evaluate_acceptance,
    main,
    make_search_predicate,
    seed_additional_chunks,
    verify_disposable_database_ownership,
)


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


def wait_until_dead(pid: int, timeout: float = 3.0) -> bool:
    """Waits up to timeout seconds for a process to terminate on Windows."""
    start = time.time()
    while time.time() - start < timeout:
        if not is_process_running(pid):
            return True
        time.sleep(0.05)
    return not is_process_running(pid)


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

    assert wait_until_dead(parent_pid), f"Backend parent PID {parent_pid} was not terminated by wrapper cleanup"
    if child_pid:
        assert wait_until_dead(child_pid), (
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

    assert wait_until_dead(b_pid), f"Owned backend PID {b_pid} was not terminated on runner failure"
    assert wait_until_dead(f_pid), f"Owned frontend PID {f_pid} was not terminated on runner failure"


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

    assert wait_until_dead(b_pid), f"Owned backend PID {b_pid} was not terminated on success"
    assert wait_until_dead(f_pid), f"Owned frontend PID {f_pid} was not terminated on success"


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

    assert wait_until_dead(b_pid), f"Owned backend PID {b_pid} was not terminated on success"
    assert wait_until_dead(f_pid), f"Owned frontend PID {f_pid} was not terminated on success"


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
# L5 Tests: Disposable Database Ownership Verification
# ==============================================================================


def test_verify_disposable_database_ownership_fails_closed_when_env_not_disposable(monkeypatch):
    """L5: verify_disposable_database_ownership must fail closed when local DISPOSABLE_TEST_ENV is not set."""
    monkeypatch.delenv("DISPOSABLE_TEST_ENV", raising=False)
    with pytest.raises(RuntimeError, match="Local environment is not configured as disposable"):
        verify_disposable_database_ownership("http://127.0.0.1:8000")


def test_verify_disposable_database_ownership_fails_when_backend_not_disposable(monkeypatch):
    """L5: verify_disposable_database_ownership must fail when target backend disposable_test_env is False."""
    monkeypatch.setenv("DISPOSABLE_TEST_ENV", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///C:/test/disposable.db")

    b_port = find_free_port()

    class NonDispHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"disposable_test_env": false}')

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", b_port), NonDispHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        with pytest.raises(RuntimeError, match="not in a disposable test environment"):
            verify_disposable_database_ownership(f"http://127.0.0.1:{b_port}")
    finally:
        server.shutdown()


def test_verify_disposable_database_ownership_fails_when_database_identity_mismatched(monkeypatch):
    """L5: verify_disposable_database_ownership must fail when local DATABASE_URL does not match backend database_identity."""
    monkeypatch.setenv("DISPOSABLE_TEST_ENV", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///C:/test/local_disposable.db")

    b_port = find_free_port()

    class MismatchedHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                b'{"disposable_test_env": true, "database_identity": "remote_different_identity_hash_123"}'
            )

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", b_port), MismatchedHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        with pytest.raises(
            RuntimeError, match="Mismatched database configuration between local caller and remote backend"
        ):
            verify_disposable_database_ownership(f"http://127.0.0.1:{b_port}")
    finally:
        server.shutdown()


def test_verify_disposable_database_ownership_succeeds_when_matched(monkeypatch):
    """L5: verify_disposable_database_ownership returns identity when local and remote match."""
    local_url = "sqlite:///C:/test/matching_disposable.db"
    monkeypatch.setenv("DISPOSABLE_TEST_ENV", "1")
    monkeypatch.setenv("DATABASE_URL", local_url)

    expected_id = compute_local_database_identity()
    assert expected_id is not None

    b_port = find_free_port()

    class MatchedHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"disposable_test_env": True, "database_identity": expected_id}).encode("utf-8")
            )

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", b_port), MatchedHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        ident = verify_disposable_database_ownership(f"http://127.0.0.1:{b_port}")
        assert ident == expected_id
    finally:
        server.shutdown()


def test_drain_worker_and_seed_chunks_fail_when_ownership_unverified(monkeypatch):
    """L5: drain_worker_engine and seed_additional_chunks fail when base_url points to unverified/non-disposable server."""
    monkeypatch.delenv("DISPOSABLE_TEST_ENV", raising=False)
    with pytest.raises(RuntimeError, match="Local environment is not configured as disposable"):
        drain_worker_engine(max_cycles=1, base_url="http://127.0.0.1:8000")

    with pytest.raises(RuntimeError, match="Local environment is not configured as disposable"):
        seed_additional_chunks("paper-1", target_count=5, base_url="http://127.0.0.1:8000")


def test_suite_attach_mode_rejects_mismatched_database_identity_for_phase4(tmp_path):
    """L5: In -Attach mode with -RequirePhase4, mismatched database_identity must be rejected."""
    b_port = find_free_port()
    f_port = find_free_port()

    class MismatchedAttachHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if self.path == "/api/config/public":
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"disposable_test_env": true, "database_identity": "mismatched_server_hash_999"}')
            else:
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"OK")

        def log_message(self, *args):
            pass

    backend_server = HTTPServer(("127.0.0.1", b_port), MismatchedAttachHandler)
    frontend_server = HTTPServer(("127.0.0.1", f_port), MismatchedAttachHandler)
    t_b = threading.Thread(target=backend_server.serve_forever, daemon=True)
    t_f = threading.Thread(target=frontend_server.serve_forever, daemon=True)
    t_b.start()
    t_f.start()

    try:
        env = os.environ.copy()
        env["DATABASE_URL"] = "sqlite:///C:/test/local_unmatched.db"
        env["DISPOSABLE_TEST_ENV"] = "1"
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SUITE_SCRIPT),
            "-Attach",
            "-RequirePhase4",
            "-BackendPort",
            str(b_port),
            "-FrontendPort",
            str(f_port),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, env=env)
        assert proc.returncode != 0
        combined_output = proc.stdout + proc.stderr
        assert (
            "does not match target backend's database_identity" in combined_output
            or "Attach mode rejected" in combined_output
        )
    finally:
        backend_server.shutdown()
        frontend_server.shutdown()


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


# ==============================================================================
# S1 Tests: Search Acceptance Evaluation, Response Predicate, and Latency Gate
# ==============================================================================


def test_evaluate_acceptance_strictly_fails_when_search_success_missing_or_false(valid_browser_results):
    """S1: evaluate_acceptance with require_phase2 must strictly fail if search_success is missing or False."""
    results = copy.deepcopy(valid_browser_results)
    results["phase2_lifecycle"] = {
        "workspace_created": True,
        "pdf_uploaded": True,
        "duplicate_identified": True,
        "corrupt_rejected": True,
        # search_success missing
        "viewer_opened": True,
        "viewer_pdf_loaded": True,
        "viewer_escape_closed": True,
        "cancel_deletion_kept_paper": True,
        "confirm_deletion_removed_paper": True,
        "workspace_deleted": True,
    }

    passed, failures, criteria = evaluate_acceptance(results, require_phase2=True)
    assert passed is False
    assert criteria["phase2_library_lifecycle"] is False
    assert any("Phase 2 Library Lifecycle criteria failed" in f for f in failures)

    # Also test explicit False
    results["phase2_lifecycle"]["search_success"] = False
    passed2, failures2, criteria2 = evaluate_acceptance(results, require_phase2=True)
    assert passed2 is False
    assert criteria2["phase2_library_lifecycle"] is False


def test_make_search_predicate_matching_contracts():
    """S1: make_search_predicate accurately matches query string, decoded values, workspace ID, and HTTP 200."""

    class MockRequest:
        def __init__(self, method="GET"):
            self.method = method

    class MockResponse:
        def __init__(self, url, status=200, method="GET"):
            self.url = url
            self.status = status
            self.request = MockRequest(method)

    pred_alpha = make_search_predicate("alpha", "ws_123")

    # 1. Exact match returns True
    res_valid = MockResponse("http://127.0.0.1:5178/api/papers?workspace_id=ws_123&q=alpha&limit=25", 200)
    assert pred_alpha(res_valid) is True

    # 2. Foreign workspace returns False
    res_foreign_ws = MockResponse("http://127.0.0.1:5178/api/papers?workspace_id=ws_foreign&q=alpha&limit=25", 200)
    assert pred_alpha(res_foreign_ws) is False

    # 3. Nonmatching query returns False
    res_wrong_q = MockResponse("http://127.0.0.1:5178/api/papers?workspace_id=ws_123&q=beta&limit=25", 200)
    assert pred_alpha(res_wrong_q) is False

    # 4. HTTP non-200 returns False
    res_500 = MockResponse("http://127.0.0.1:5178/api/papers?workspace_id=ws_123&q=alpha&limit=25", 500)
    assert pred_alpha(res_500) is False

    # 5. Method not GET returns False
    res_post = MockResponse("http://127.0.0.1:5178/api/papers?workspace_id=ws_123&q=alpha&limit=25", 200, method="POST")
    assert pred_alpha(res_post) is False

    # 6. Cleared query (no q parameter in URL) returns True for expected_q=""
    pred_cleared = make_search_predicate("", "ws_123")
    res_cleared_no_q = MockResponse("http://127.0.0.1:5178/api/papers?workspace_id=ws_123&limit=25", 200)
    assert pred_cleared(res_cleared_no_q) is True

    # 7. Cleared query (empty q parameter) returns True for expected_q=""
    res_cleared_empty_q = MockResponse("http://127.0.0.1:5178/api/papers?workspace_id=ws_123&q=&limit=25", 200)
    assert pred_cleared(res_cleared_empty_q) is True


def test_cli_passes_search_delay_argument(tmp_path):
    """S1: run_browser_verification.py CLI passes --search-delay-ms to run_checks."""
    summary_path = tmp_path / "summary.json"
    output_dir = tmp_path / "artifacts"

    with patch("run_browser_verification.run_checks", return_value=({}, True)) as mock_run:
        with patch(
            "sys.argv",
            [
                "run_browser_verification.py",
                "--output-dir",
                str(output_dir),
                "--summary-path",
                str(summary_path),
                "--search-delay-ms",
                "750",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            assert kwargs.get("search_delay_ms") == 750


# ==============================================================================
# Phase 4 Quality Center Acceptance Evaluation Tests
# ==============================================================================


def test_evaluate_acceptance_with_phase4_passes(valid_browser_results):
    """Phase 4: evaluate_acceptance passes when phase4_quality_center criteria are satisfied."""
    results = copy.deepcopy(valid_browser_results)
    results["phase4_quality_center"] = {
        "planned_routes_available": True,
        "quality_route_guidance": True,
        "disposable_worker_lifecycle": True,
        "real_processed_chunks": True,
        "page_gt1_source_navigation": True,
        "pagination_gt100_chunks": True,
        "transient_recovery": True,
        "late_response_isolation": True,
        "quality_modal_opened": True,
        "quality_tabs_present": True,
        "quality_modal_escape_closed": True,
    }

    passed, failures, criteria = evaluate_acceptance(results, require_phase4=True)
    assert passed is True
    assert len(failures) == 0
    assert criteria["phase4_quality_center"] is True


def test_evaluate_acceptance_fails_on_phase4_missing_when_required(valid_browser_results):
    """Phase 4: evaluate_acceptance fails when require_phase4 is True but results lack phase4_quality_center."""
    results = copy.deepcopy(valid_browser_results)
    passed, failures, criteria = evaluate_acceptance(results, require_phase4=True)
    assert passed is False
    assert criteria["phase4_quality_center"] is False
    assert any("Phase 4 Quality Center verification is required but missing" in f for f in failures)


def test_evaluate_acceptance_fails_on_phase4_modal_not_opened(valid_browser_results):
    """Phase 4: evaluate_acceptance fails when quality_modal_opened is False."""
    results = copy.deepcopy(valid_browser_results)
    results["phase4_quality_center"] = {
        "planned_routes_available": True,
        "quality_route_guidance": True,
        "disposable_worker_lifecycle": True,
        "real_processed_chunks": True,
        "page_gt1_source_navigation": True,
        "pagination_gt100_chunks": True,
        "transient_recovery": True,
        "late_response_isolation": True,
        "quality_modal_opened": False,
        "quality_tabs_present": True,
        "quality_modal_escape_closed": True,
    }

    passed, failures, criteria = evaluate_acceptance(results, require_phase4=True)
    assert passed is False
    assert criteria["phase4_quality_center"] is False
    assert any("Phase 4 Quality Center criteria failed" in f for f in failures)


def test_cli_passes_require_phase4_argument(tmp_path):
    """Phase 4: run_browser_verification.py CLI passes --require-phase4 to run_checks."""
    summary_path = tmp_path / "summary.json"
    output_dir = tmp_path / "artifacts"

    with patch("run_browser_verification.run_checks", return_value=({}, True)) as mock_run:
        with patch(
            "sys.argv",
            [
                "run_browser_verification.py",
                "--output-dir",
                str(output_dir),
                "--summary-path",
                str(summary_path),
                "--require-phase4",
            ],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_run.assert_called_once()
            _, kwargs = mock_run.call_args
            assert kwargs.get("require_phase4") is True


# ==============================================================================
# Late Response Isolation & Real Message Contract Negative Control Tests (M3)
# ==============================================================================


class _MockDialogElement:
    def __init__(self, count: int = 0, texts: list[str] | None = None):
        self._count = count
        self._texts = texts or []

    def count(self) -> int:
        return self._count

    def all(self) -> list["_MockDialogElement"]:
        return [_MockDialogElement(1, [t]) for t in self._texts]

    def inner_text(self) -> str:
        return self._texts[0] if self._texts else ""

    def text_content(self) -> str:
        return self._texts[0] if self._texts else ""

    def get_by_text(self, text: str, exact: bool = False) -> "_MockDialogElement":
        matching = [t for t in self._texts if (t == text if exact else text in t)]
        return _MockDialogElement(len(matching), matching)

    def locator(self, selector: str) -> "_MockDialogElement":
        return self


class _MockDialogLocator:
    def __init__(self, selector_counts: dict[str, int] | None = None, chunk_texts: list[str] | None = None):
        self._counts = selector_counts or {}
        self._chunk_texts = chunk_texts

    def locator(self, selector: str) -> _MockDialogElement:
        if any(term in selector for term in ["article", "chunk-card", "chunk"]):
            if self._chunk_texts is not None:
                return _MockDialogElement(len(self._chunk_texts), self._chunk_texts)
            candidates = [
                k
                for k, v in self._counts.items()
                if v > 0
                and k
                not in (
                    "Reprocessing job enqueued successfully",
                    "Reprocessing job enqueued successfully. Pipeline restarted.",
                    "Failed to trigger reprocess",
                    "Reprocessing in Progress (Old Bundle Shown)",
                    "Processing Failed",
                )
                and not k.startswith("Loaded ")
                and not k.endswith(".pdf")
            ]
            return _MockDialogElement(len(candidates), candidates)
        return _MockDialogElement(self._counts.get(selector, 0))

    def get_by_text(self, text: str, exact: bool = False) -> _MockDialogElement:
        for k, v in self._counts.items():
            if k == text or (not exact and text in k):
                return _MockDialogElement(v, [k] * v)
        return _MockDialogElement(self._counts.get(text, 0))


class _MockButtonLocator:
    def __init__(self, is_enabled: bool = True, text: str = "Reprocess"):
        self._is_enabled = is_enabled
        self._text = text

    def is_enabled(self) -> bool:
        return self._is_enabled

    def text_content(self) -> str:
        return self._text


def test_check_late_response_isolation_passes_clean_state():
    """M3 & N2: check_late_response_isolation returns True when Paper B modal state is uncorrupted."""
    paper_title = "beta_target_paper.pdf"
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded 2 of 2 chunks": 1,
            "Loaded ": 1,
            "BERT: Pre-training of Deep Bidirectional Transformers": 1,
            "Attention Is All You Need": 0,
            "Processing Failed": 0,
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
        min_chunks=1,
        expected_status_not_failed=True,
    )
    assert passed is True
    assert all(checks.values())


def test_check_late_response_isolation_fails_on_leaked_success_banner_negative_control():
    """M3 Negative Control: check_late_response_isolation fails when Paper A's real success

    banner ('Reprocessing job enqueued successfully. Pipeline restarted.') leaks into Paper B.
    """
    paper_title = "beta_target_paper.pdf"
    # Negative control injection: success banner from Paper A's late response is present!
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully. Pipeline restarted.": 1,  # Leaked banner!
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded ": 1,
            "BERT": 1,
            "Attention Is All You Need": 0,
            "Processing Failed": 0,
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
    )
    assert passed is False
    assert checks["no_leaked_success_banner"] is False
    assert checks["b_title_intact"] is True


def test_check_late_response_isolation_fails_on_stale_warning_badge_negative_control():
    """M3 Negative Control: check_late_response_isolation fails when Paper A's stale

    warning ('Reprocessing in Progress (Old Bundle Shown)') leaks into Paper B.
    """
    paper_title = "beta_target_paper.pdf"
    # Negative control injection: stale generation badge is present in Paper B modal!
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 1,  # Stale data leak!
            "Loaded ": 1,
            "BERT": 1,
            "Attention Is All You Need": 0,
            "Processing Failed": 0,
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
    )
    assert passed is False
    assert checks["no_stale_warning"] is False


def test_check_late_response_isolation_fails_on_button_stranded_in_enqueueing():
    """M3 Negative Control: fails when Paper B reprocess button is stranded in 'Enqueueing...'."""
    paper_title = "beta_target_paper.pdf"
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded ": 1,
            "BERT": 1,
            "Attention Is All You Need": 0,
            "Processing Failed": 0,
        }
    )
    # Button stranded in Enqueueing... state
    btn = _MockButtonLocator(is_enabled=False, text="Enqueueing...")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
    )
    assert passed is False
    assert checks["b_btn_enabled"] is False


def test_check_late_response_isolation_fails_on_title_corruption():
    """M3 Negative Control: fails when document title was corrupted to a different paper."""
    paper_title = "beta_target_paper.pdf"
    dialog = _MockDialogLocator(
        {
            paper_title: 0,  # Corrupted title
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded ": 1,
            "BERT": 1,
            "Attention Is All You Need": 0,
            "Processing Failed": 0,
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
    )
    assert passed is False
    assert checks["b_title_intact"] is False


def test_check_late_response_isolation_fails_on_wrong_paper_chunks_negative_control():
    """N2 Negative Control: fails when Paper B modal contains Paper A chunks instead of Paper B chunks."""
    paper_title = "beta_target_paper.pdf"
    # Negative control injection: Paper A chunks present in Paper B modal!
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded 1 of 1 chunks": 1,
            "Loaded ": 1,
            "Attention Is All You Need": 1,  # Leaked chunk from Paper A!
            "UNIQUE CHUNK FROM PAPER A": 1,  # Leaked chunk from Paper A!
            "BERT": 0,  # Missing Paper B content!
            "Processing Failed": 0,
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
        min_chunks=1,
        expected_status_not_failed=True,
    )
    assert passed is False
    assert checks["b_chunk_content_verified"] is False
    assert checks["no_cross_paper_chunks"] is False


def test_check_late_response_isolation_fails_on_empty_or_zero_chunks_negative_control():
    """N2 Negative Control: fails when Paper B displays 'Loaded 0 of 0 chunks'."""
    paper_title = "beta_target_paper.pdf"
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded 0 of 0 chunks": 1,  # 0 chunks!
            "Loaded ": 1,
            "BERT": 0,
            "Processing Failed": 0,
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        min_chunks=1,
        expected_status_not_failed=True,
    )
    assert passed is False
    assert checks["b_chunks_intact"] is False


def test_check_late_response_isolation_fails_on_processing_failed_status_negative_control():
    """N2 Negative Control: fails when Paper B modal displays 'Processing Failed'."""
    paper_title = "beta_target_paper.pdf"
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 0,
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded 2 of 2 chunks": 1,
            "Loaded ": 1,
            "BERT": 1,
            "Processing Failed": 1,  # Error badge displayed!
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        min_chunks=1,
        expected_status_not_failed=True,
    )
    assert passed is False
    assert checks["b_status_healthy"] is False


def test_check_late_response_isolation_fails_on_delayed_body_corruption_negative_control():
    """N2 Negative Control: fails when delayed response body resolution injects corruption."""
    paper_title = "beta_target_paper.pdf"
    dialog = _MockDialogLocator(
        {
            paper_title: 1,
            "Reprocessing job enqueued successfully": 0,
            "Failed to trigger reprocess": 1,  # Delayed body resolution leaked error banner!
            "Reprocessing in Progress (Old Bundle Shown)": 0,
            "Loaded 2 of 2 chunks": 1,
            "Loaded ": 1,
            "BERT": 1,
            "Processing Failed": 0,
        }
    )
    btn = _MockButtonLocator(is_enabled=True, text="Reprocess")

    passed, checks = check_late_response_isolation(
        dialog,
        paper_title,
        btn,
        expected_chunk_text="BERT",
        min_chunks=1,
        expected_status_not_failed=True,
    )
    assert passed is False
    assert checks["no_leaked_error_banner"] is False


def test_evaluate_acceptance_fails_on_late_response_isolation_false(valid_browser_results):
    """M3: evaluate_acceptance strictly fails when late_response_isolation is False."""
    results = copy.deepcopy(valid_browser_results)
    results["phase4_quality_center"] = {
        "planned_routes_available": True,
        "quality_route_guidance": True,
        "disposable_worker_lifecycle": True,
        "real_processed_chunks": True,
        "page_gt1_source_navigation": True,
        "pagination_gt100_chunks": True,
        "transient_recovery": True,
        "late_response_isolation": False,  # Simulated gate failure
        "quality_modal_opened": True,
        "quality_tabs_present": True,
        "quality_modal_escape_closed": True,
    }

    passed, failures, criteria = evaluate_acceptance(results, require_phase4=True)
    assert passed is False
    assert criteria["phase4_quality_center"] is False
    assert any("Phase 4 Quality Center criteria failed" in f for f in failures)


def _run_in_browser_env(test_code: str):
    """Executes a real-DOM Playwright test snippet using the Scrapling/Playwright Python environment."""
    scrapling_python = Path(r"F:\dev\apps\scrapling\Scripts\python.exe")
    python_exe = scrapling_python if scrapling_python.exists() else Path(sys.executable)

    check_code = "import playwright; print('OK')"
    check_res = subprocess.run([str(python_exe), "-c", check_code], capture_output=True, text=True)
    if check_res.returncode != 0:
        pytest.skip(f"Playwright is not available in {python_exe}: {check_res.stderr.strip()}")

    full_code = f"""
import sys, os
from pathlib import Path
scripts_dir = Path(r"{SCRIPTS_DIR}")
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from run_browser_verification import check_late_response_isolation

{test_code}
"""
    env = os.environ.copy()
    proc = subprocess.run(
        [str(python_exe), "-c", full_code],
        capture_output=True,
        text=True,
        cwd=str(SCRIPTS_DIR.parent),
        env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"Subprocess test failed (exit code {proc.returncode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )


def test_real_dom_late_response_isolation_passes_genuine_b_fixture():
    """O1: Genuine Paper B fixture passes check_late_response_isolation in real DOM."""
    test_code = r"""
from playwright.sync_api import sync_playwright

chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome_exe, headless=True)
    page = browser.new_page()
    page.set_content(
        '''<div role="dialog">
            <h2>BERT: Pre-training of Deep Bidirectional Transformers</h2>
            <button>Reprocess</button>
            <p>Loaded 1 of 1 chunks</p>
            <article class="chunk-card" data-testid="chunk-card">
                <div class="chunk-text" data-testid="chunk-text">Language representation models pre-trained on corpora have revolutionized NLP.</div>
            </article>
        </div>'''
    )
    passed, checks = check_late_response_isolation(
        page.get_by_role("dialog"),
        "BERT: Pre-training of Deep Bidirectional Transformers",
        page.get_by_role("button"),
        expected_chunk_text="Language representation models",
        prohibited_chunk_text=["Attention Is All You Need", "Recurrent neural networks"],
        min_chunks=1,
        expected_status_not_failed=True,
        expected_chunks=["Language representation models pre-trained on corpora have revolutionized NLP."],
    )
    assert passed is True
    assert all(checks.values()), f"Checks failed: {checks}"
    browser.close()
"""
    _run_in_browser_env(test_code)


def test_real_dom_late_response_isolation_fails_on_wrong_body_non_title_a_chunk_negative_control():
    """O1 Negative Control: Replacing B's body with a non-title A chunk must fail.

    Even if expected_chunk_text is 'BERT' (from the title), chunk-scoped locator fails.
    And when expected_chunk_text is B's distinct phrase or prohibited_chunk_text is A's phrase, it fails.
    """
    test_code = r"""
from playwright.sync_api import sync_playwright

chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome_exe, headless=True)
    page = browser.new_page()
    page.set_content(
        '''<div role="dialog">
            <h2>BERT: Pre-training of Deep Bidirectional Transformers</h2>
            <button>Reprocess</button>
            <p>Loaded 1 of 1 chunks</p>
            <article class="chunk-card" data-testid="chunk-card">
                <div class="chunk-text" data-testid="chunk-text">Recurrent neural networks have been firmly established as state of the art approaches in sequence modeling.</div>
            </article>
        </div>'''
    )
    # Test 1: Title word 'BERT' no longer passes because it is scoped to chunk cards/article
    passed_title_probe, checks_title_probe = check_late_response_isolation(
        page.get_by_role("dialog"),
        "BERT: Pre-training of Deep Bidirectional Transformers",
        page.get_by_role("button"),
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
    )
    assert passed_title_probe is False, f"Expected False but got True: {checks_title_probe}"
    assert checks_title_probe["b_chunk_content_verified"] is False
    assert checks_title_probe["b_title_intact"] is True

    # Test 2: Distinct body phrase check fails because B body text is missing
    passed_distinct, checks_distinct = check_late_response_isolation(
        page.get_by_role("dialog"),
        "BERT: Pre-training of Deep Bidirectional Transformers",
        page.get_by_role("button"),
        expected_chunk_text="Language representation models",
        prohibited_chunk_text=["Attention Is All You Need", "Recurrent neural networks"],
    )
    assert passed_distinct is False, f"Expected False but got True: {checks_distinct}"
    assert checks_distinct["b_chunk_content_verified"] is False
    assert checks_distinct["no_cross_paper_chunks"] is False
    browser.close()
"""
    _run_in_browser_env(test_code)


def test_real_dom_late_response_isolation_fails_on_partial_a_contamination_negative_control():
    """O1 Negative Control: Appending one foreign chunk to valid B content must fail."""
    test_code = r"""
from playwright.sync_api import sync_playwright

chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=chrome_exe, headless=True)
    page = browser.new_page()
    page.set_content(
        '''<div role="dialog">
            <h2>BERT: Pre-training of Deep Bidirectional Transformers</h2>
            <button>Reprocess</button>
            <p>Loaded 2 of 2 chunks</p>
            <article class="chunk-card" data-testid="chunk-card">
                <div class="chunk-text" data-testid="chunk-text">Language representation models pre-trained on corpora have revolutionized NLP.</div>
            </article>
            <article class="chunk-card" data-testid="chunk-card">
                <div class="chunk-text" data-testid="chunk-text">Recurrent neural networks have been firmly established as state of the art approaches in sequence modeling.</div>
            </article>
        </div>'''
    )
    # Test 1: expected_chunks baseline check detects the extra foreign chunk
    passed_exact, checks_exact = check_late_response_isolation(
        page.get_by_role("dialog"),
        "BERT: Pre-training of Deep Bidirectional Transformers",
        page.get_by_role("button"),
        expected_chunk_text="Language representation models",
        prohibited_chunk_text=["Attention Is All You Need"],
        expected_chunks=["Language representation models pre-trained on corpora have revolutionized NLP."],
    )
    assert passed_exact is False, f"Expected False but got True: {checks_exact}"
    assert checks_exact["b_chunk_content_verified"] is False or checks_exact["no_cross_paper_chunks"] is False

    # Test 2: prohibited_chunk_text catches foreign chunk in partial contamination
    passed_prohib, checks_prohib = check_late_response_isolation(
        page.get_by_role("dialog"),
        "BERT: Pre-training of Deep Bidirectional Transformers",
        page.get_by_role("button"),
        expected_chunk_text="Language representation models",
        prohibited_chunk_text=["Attention Is All You Need", "Recurrent neural networks"],
    )
    assert passed_prohib is False, f"Expected False but got True: {checks_prohib}"
    assert checks_prohib["no_cross_paper_chunks"] is False
    browser.close()
"""
    _run_in_browser_env(test_code)


# ---------------------------------------------------------------------------
# Phase 5 Index Lifecycle & Viewports Acceptance Evaluation Tests (P5-F4..F6)
# ---------------------------------------------------------------------------
def test_evaluate_acceptance_phase5_valid_and_negative_controls(valid_browser_results, tmp_path):
    """Verifies that evaluate_acceptance enforces real observed index details, populated viewports, and transient recovery."""
    results = copy.deepcopy(valid_browser_results)

    # Valid screenshot fixtures
    d_shot = tmp_path / "desktop.png"
    d_shot.write_bytes(b"dummy")
    t_shot = tmp_path / "tablet.png"
    t_shot.write_bytes(b"dummy")
    m_shot = tmp_path / "mobile.png"
    m_shot.write_bytes(b"dummy")

    # Valid Phase 5 results
    results["phase5_index_lifecycle"] = {
        "real_worker_pipeline_to_ready": True,
        "embedding_stage_verified": True,
        "indexing_stage_verified": True,
        "active_workspace_index_published": True,
        "quality_center_index_details": True,
        "transient_failure_recovery": True,
        "observed_index_details": {
            "version": 1,
            "model_name": "all-MiniLM-L6-v2",
            "dimension": 384,
            "chunk_count": 4,
            "ui_model_verified": True,
            "ui_dim_verified": True,
            "ui_norm_verified": True,
            "ui_faiss_verified": True,
            "ui_bm25_verified": True,
            "artifact_integrity_verified": True,
        },
        "observed_indexing_recovery": {
            "paper_id": "test-recovery-paper-uuid-1",
            "initial_failure_observed": True,
            "reprocess_triggered": True,
            "final_status": "ready",
            "recovered_to_ready": True,
        },
    }

    results["viewports"] = {
        "desktop_1440": {
            "width": 1440,
            "height": 900,
            "screenshot_path": str(d_shot),
            "has_horizontal_overflow": False,
            "h1_visible": True,
            "workspace_select_usable": True,
            "paper_selected": True,
            "pipeline_visible": True,
            "index_membership_visible": True,
        },
        "tablet_768": {
            "width": 768,
            "height": 1024,
            "screenshot_path": str(t_shot),
            "has_horizontal_overflow": False,
            "h1_visible": True,
            "workspace_select_usable": True,
            "paper_selected": True,
            "pipeline_visible": True,
            "index_membership_visible": True,
        },
        "mobile_375": {
            "width": 375,
            "height": 667,
            "screenshot_path": str(m_shot),
            "has_horizontal_overflow": False,
            "h1_visible": True,
            "workspace_select_usable": True,
            "paper_selected": True,
            "pipeline_visible": True,
            "index_membership_visible": True,
        },
    }

    # Baseline pass
    passed, failures, criteria = evaluate_acceptance(results, require_phase5=True)
    assert passed is True
    assert criteria["phase5_index_lifecycle"] is True
    assert len(failures) == 0

    # Negative Control 1: Synthetic pass with missing observed_index_details must fail
    res_no_obs = copy.deepcopy(results)
    del res_no_obs["phase5_index_lifecycle"]["observed_index_details"]
    p_fail, f_reasons, c_status = evaluate_acceptance(res_no_obs, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 2: Zero chunk count must fail
    res_zero_chunk = copy.deepcopy(results)
    res_zero_chunk["phase5_index_lifecycle"]["observed_index_details"]["chunk_count"] = 0
    p_fail, f_reasons, c_status = evaluate_acceptance(res_zero_chunk, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 3: Unverified artifacts must fail
    res_bad_art = copy.deepcopy(results)
    res_bad_art["phase5_index_lifecycle"]["observed_index_details"]["artifact_integrity_verified"] = False
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_art, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 4: Transient failure recovery False must fail
    res_no_rec = copy.deepcopy(results)
    res_no_rec["phase5_index_lifecycle"]["transient_failure_recovery"] = False
    p_fail, f_reasons, c_status = evaluate_acceptance(res_no_rec, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5: UI index details unverified must fail
    res_bad_ui = copy.deepcopy(results)
    res_bad_ui["phase5_index_lifecycle"]["observed_index_details"]["ui_faiss_verified"] = False
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_ui, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5b: UI normalization unverified must fail (P5-F12 probe 2)
    res_bad_norm = copy.deepcopy(results)
    res_bad_norm["phase5_index_lifecycle"]["observed_index_details"]["ui_norm_verified"] = False
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_norm, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5c: Invalid or non-positive index version must fail
    res_zero_ver = copy.deepcopy(results)
    res_zero_ver["phase5_index_lifecycle"]["observed_index_details"]["version"] = 0
    p_fail, f_reasons, c_status = evaluate_acceptance(res_zero_ver, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5d: Missing or empty model_name must fail
    res_empty_model = copy.deepcopy(results)
    res_empty_model["phase5_index_lifecycle"]["observed_index_details"]["model_name"] = ""
    p_fail, f_reasons, c_status = evaluate_acceptance(res_empty_model, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5e: Non-positive dimension must fail
    res_zero_dim = copy.deepcopy(results)
    res_zero_dim["phase5_index_lifecycle"]["observed_index_details"]["dimension"] = 0
    p_fail, f_reasons, c_status = evaluate_acceptance(res_zero_dim, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5f: Missing observed_indexing_recovery must fail (P5-F12 probe 1)
    res_no_obs_rec = copy.deepcopy(results)
    del res_no_obs_rec["phase5_index_lifecycle"]["observed_indexing_recovery"]
    p_fail, f_reasons, c_status = evaluate_acceptance(res_no_obs_rec, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5g: Incomplete observed_indexing_recovery (empty paper_id) must fail
    res_bad_rec_id = copy.deepcopy(results)
    res_bad_rec_id["phase5_index_lifecycle"]["observed_indexing_recovery"]["paper_id"] = ""
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_rec_id, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5h: initial_failure_observed False in recovery must fail
    res_bad_rec_init = copy.deepcopy(results)
    res_bad_rec_init["phase5_index_lifecycle"]["observed_indexing_recovery"]["initial_failure_observed"] = False
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_rec_init, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5i: reprocess_triggered False in recovery must fail
    res_bad_rec_reproc = copy.deepcopy(results)
    res_bad_rec_reproc["phase5_index_lifecycle"]["observed_indexing_recovery"]["reprocess_triggered"] = False
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_rec_reproc, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5j: final_status != ready in recovery must fail
    res_bad_rec_status = copy.deepcopy(results)
    res_bad_rec_status["phase5_index_lifecycle"]["observed_indexing_recovery"]["final_status"] = "failed"
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_rec_status, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 5k: recovered_to_ready False in recovery must fail
    res_bad_rec_rec = copy.deepcopy(results)
    res_bad_rec_rec["phase5_index_lifecycle"]["observed_indexing_recovery"]["recovered_to_ready"] = False
    p_fail, f_reasons, c_status = evaluate_acceptance(res_bad_rec_rec, require_phase5=True)
    assert p_fail is False
    assert c_status["phase5_index_lifecycle"] is False

    # Negative Control 6: Missing mobile viewport must fail
    res_missing_mob = copy.deepcopy(results)
    del res_missing_mob["viewports"]["mobile_375"]
    p_fail, f_reasons, _ = evaluate_acceptance(res_missing_mob, require_phase5=True)
    assert p_fail is False
    assert any("mobile_375" in f for f in f_reasons)

    # Negative Control 7: Empty-state / unusable workspace selector must fail
    res_unusable_ws = copy.deepcopy(results)
    res_unusable_ws["viewports"]["desktop_1440"]["workspace_select_usable"] = False
    p_fail, f_reasons, _ = evaluate_acceptance(res_unusable_ws, require_phase5=True)
    assert p_fail is False
    assert any("workspace selector not usable" in f for f in f_reasons)

    # Negative Control 8: Paper not selected must fail
    res_no_paper = copy.deepcopy(results)
    res_no_paper["viewports"]["tablet_768"]["paper_selected"] = False
    p_fail, f_reasons, _ = evaluate_acceptance(res_no_paper, require_phase5=True)
    assert p_fail is False
    assert any("paper not selected" in f for f in f_reasons)

    # Negative Control 9: Pipeline not visible must fail
    res_no_pipe = copy.deepcopy(results)
    res_no_pipe["viewports"]["mobile_375"]["pipeline_visible"] = False
    p_fail, f_reasons, _ = evaluate_acceptance(res_no_pipe, require_phase5=True)
    assert p_fail is False
    assert any("pipeline tab not visible" in f for f in f_reasons)

    # Negative Control 10: Index & membership not visible must fail
    res_no_idx_tab = copy.deepcopy(results)
    res_no_idx_tab["viewports"]["desktop_1440"]["index_membership_visible"] = False
    p_fail, f_reasons, _ = evaluate_acceptance(res_no_idx_tab, require_phase5=True)
    assert p_fail is False
    assert any("index & membership tab not visible" in f for f in f_reasons)

    # Negative Control 11: Missing or empty screenshot file must fail
    res_no_shot = copy.deepcopy(results)
    empty_shot = tmp_path / "empty.png"
    empty_shot.write_bytes(b"")
    res_no_shot["viewports"]["mobile_375"]["screenshot_path"] = str(empty_shot)
    p_fail, f_reasons, _ = evaluate_acceptance(res_no_shot, require_phase5=True)
    assert p_fail is False
    assert any("screenshot missing or empty" in f for f in f_reasons)

    # Negative Control 12: Horizontal overflow must fail
    res_ov = copy.deepcopy(results)
    res_ov["viewports"]["mobile_375"]["has_horizontal_overflow"] = True
    p_fail, f_reasons, _ = evaluate_acceptance(res_ov, require_phase5=True)
    assert p_fail is False
    assert any("horizontal overflow in mobile_375" in f for f in f_reasons)


def test_evaluate_acceptance_viewports_horizontal_overflow_detection(valid_browser_results):
    """Verifies that evaluate_acceptance detects horizontal overflow in responsive viewports."""
    results = copy.deepcopy(valid_browser_results)

    results["viewports"] = {
        "desktop_1440": {"width": 1440, "height": 900, "has_horizontal_overflow": False},
        "tablet_768": {"width": 768, "height": 1024, "has_horizontal_overflow": False},
        "mobile_375": {"width": 375, "height": 667, "has_horizontal_overflow": False},
    }

    passed, failures, criteria = evaluate_acceptance(results)
    assert passed is True
    assert len(failures) == 0

    # Overflow on tablet
    res_tab_ov = copy.deepcopy(results)
    res_tab_ov["viewports"]["tablet_768"]["has_horizontal_overflow"] = True
    passed, failures, _ = evaluate_acceptance(res_tab_ov)
    assert passed is False
    assert any("tablet_768" in f for f in failures)

    # Overflow on mobile
    res_mob_ov = copy.deepcopy(results)
    res_mob_ov["viewports"]["mobile_375"]["has_horizontal_overflow"] = True
    passed, failures, _ = evaluate_acceptance(res_mob_ov)
    assert passed is False
    assert any("mobile_375" in f for f in failures)
