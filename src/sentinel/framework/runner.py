"""
Standalone runner for the Sentinel Framework.

Provides a simple run() function for standalone applications.
"""

import asyncio
import logging
import signal
from typing import Optional

from sentinel.framework.basing import AppBaser
from sentinel.framework.watching import FileWatchingService
from sentinel.framework.registry import get_registry

logger = logging.getLogger(__name__)


def run(
    export_dir: str,
    poll_interval: float = 2.0,
    name: Optional[str] = None,
    base: str = "",
    bran: Optional[str] = None,
    hby=None,
    rgy=None,
    db=None,
):
    """
    Run the file watching service with registered handlers.

    This is the main entry point for standalone applications.
    Blocks until SIGINT/SIGTERM received.

    Args:
        export_dir: Base export directory to watch (e.g., /usr/local/sentinel)
        poll_interval: Polling interval in seconds (default: 2.0)
        name: Optional database name for KERI operations
        base: Optional base directory for KERI database
        bran: Optional passcode for KERI database
        hby: Optional pre-configured Habery instance
        rgy: Optional pre-configured Regery instance
        db: Optional pre-configured database

    Example:
        from sentinel.framework import EventHandler, register_handler, run

        class MyHandler(EventHandler):
            async def on_kel(self, event):
                print(f"KEL: {event.aid}")

        register_handler(MyHandler())
        run(export_dir="/usr/local/sentinel")
    """
    # Check if handlers registered
    if not get_registry().get_handlers():
        logger.warning(
            "No handlers registered. Use register_handler() before calling run()"
        )
        return

    # If name provided but no hby, initialize KERI infrastructure
    if name and not hby:
        try:
            from keri.app import habbing

            hby = habbing.Habery(name=name, base=base, bran=bran)
            logger.info(f"Initialized KERI Habery: {name}")
        except Exception as e:
            logger.warning(f"Failed to initialize KERI infrastructure: {e}")
            logger.info("Continuing without KERI support")

    if not db:
        db = AppBaser(name=hby.name, headDirPath=export_dir)

    # Run async main
    asyncio.run(
        _async_run(
            export_dir=export_dir,
            poll_interval=poll_interval,
            hby=hby,
            rgy=rgy,
            db=db,
        )
    )


async def _async_run(
    export_dir: str,
    poll_interval: float,
    hby,
    rgy,
    db,
):
    """
    Async runner for the file watching service.

    Args:
        export_dir: Base export directory to watch
        poll_interval: Polling interval in seconds
        hby: Optional Habery instance
        rgy: Optional Regery instance
        db: Optional database instance
    """
    logger.info("Starting file watching service...")

    # Create service
    service = FileWatchingService(
        export_dir=export_dir,
        poll_interval=poll_interval,
        hby=hby,
        rgy=rgy,
        db=db,
    )

    # Start service
    task = service.start()

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        # Wait for shutdown signal or task completion
        done, pending = await asyncio.wait(
            [task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If shutdown requested, stop service
        if shutdown_event.is_set():
            logger.info("Stopping service...")
            service.stop()

            # Wait for task to complete with timeout
            if pending:
                await asyncio.wait(pending, timeout=5.0)

    except Exception as e:
        logger.exception(f"Error in runner: {e}")
        service.stop()
        raise
    finally:
        # Cancel remaining tasks
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    logger.info("File watching service stopped")
