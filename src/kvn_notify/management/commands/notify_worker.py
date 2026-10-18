import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections

from kvn_notify import dispatch
from kvn_notify.conf import notify_settings

CLEANUP_EVERY_SECONDS = 3600
# After a failed round (database restarting, network blip), wait this long, doubling up to the cap.
ERROR_BACKOFF_SECONDS = 5
ERROR_BACKOFF_MAX_SECONDS = 60

logger = logging.getLogger("kvn_notify")


class Command(BaseCommand):
    help = (
        "Send queued notifications. Runs until stopped; "
        "use --once from cron instead of a long-running process."
    )

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Send what is due, then exit.")
        parser.add_argument(
            "--batch", type=int, default=None, help="Deliveries per round (default: BATCH_SIZE)."
        )
        parser.add_argument(
            "--poll",
            type=float,
            default=None,
            help="Seconds to wait when the queue is empty (default: WORKER_POLL_SECONDS).",
        )

    def handle(self, *args, once=False, batch=None, poll=None, **options):
        batch = batch or notify_settings.BATCH_SIZE
        poll = poll if poll is not None else notify_settings.WORKER_POLL_SECONDS
        verbose = options.get("verbosity", 1) >= 1

        if once:
            stats = self._drain(batch)
            dispatch.cleanup()
            if verbose:
                self._report(stats)
            return

        self._running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        if verbose:
            self.stdout.write(f"kvn-notify worker started (batch {batch}, poll {poll}s). Ctrl+C to stop.")

        last_cleanup = 0.0
        backoff = ERROR_BACKOFF_SECONDS
        while self._running:
            # A long-running process never gets Django's per-request connection
            # handling, so drop connections that broke (database restart) or expired.
            close_old_connections()
            try:
                stats = dispatch.process_due(batch)
                if stats.processed and verbose:
                    self._report(stats)
                if time.monotonic() - last_cleanup > CLEANUP_EVERY_SECONDS:
                    removed = dispatch.cleanup()
                    last_cleanup = time.monotonic()
                    if removed and verbose:
                        self.stdout.write(f"Removed {removed} old notifications.")
            except Exception as exc:
                # Keep running: whatever was due stays queued and is sent on a later round.
                logger.exception("kvn-notify worker round failed; retrying in %ss", backoff)
                self.stderr.write(f"Round failed ({exc.__class__.__name__}: {exc}); retrying in {backoff}s.")
                connections.close_all()
                self._sleep(backoff)
                backoff = min(backoff * 2, ERROR_BACKOFF_MAX_SECONDS)
                continue
            backoff = ERROR_BACKOFF_SECONDS
            if stats.processed < batch:
                self._sleep(poll)
        if verbose:
            self.stdout.write("kvn-notify worker stopped.")

    def _drain(self, batch):
        total = dispatch.Stats()
        while True:
            stats = dispatch.process_due(batch)
            total.add(stats)
            if stats.processed < batch:
                return total

    def _sleep(self, seconds):
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(min(0.5, end - time.monotonic()))

    def _stop(self, *args):
        self._running = False

    def _report(self, stats):
        self.stdout.write(
            f"processed={stats.processed} sent={stats.sent} retried={stats.retried} failed={stats.failed}"
        )
        for error in stats.errors:
            self.stderr.write(f"  failed: {error}")
