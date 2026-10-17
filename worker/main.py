"""ResearchMind AI — Worker CLI Entrypoint (Phase 3).

Starts a standalone background processing worker with graceful signal handling.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from typing import Any

from worker.engine import WorkerEngine


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ResearchMind AI Document Processing Worker")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Queue polling interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--lease-timeout",
        type=int,
        default=30,
        help="Lease expiration threshold in seconds (default: 30)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum attempt retries before failing a stage (default: 3)",
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="Unique identifier for this worker instance",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single claim-and-process pass, then exit immediately",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    engine = WorkerEngine(
        worker_id=args.worker_id,
        poll_interval=args.poll_interval,
        lease_timeout_seconds=args.lease_timeout,
        max_retries=args.max_retries,
    )

    def _handle_signal(signum: int, frame: Any) -> None:
        logging.getLogger("worker").info(f"Signal {signum} received; shutting down gracefully...")
        engine.request_stop()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (ValueError, AttributeError):
        # In non-main threads or some environments, signal registration might fail
        pass

    if args.once:
        worked = engine.run_once()
        return 0 if worked else 0
    else:
        engine.run_loop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
