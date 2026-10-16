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
import sys
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
            "initial_focus_correct": True,
            "tab_containment": True,
            "shift_tab_containment": True,
            "escape_focus_restoration": True,
            "backdrop_click_closes": True,
            "background_interaction_blocked": True,
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
