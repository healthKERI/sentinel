"""
File watching service for the Sentinel Framework.

Provides polling-based file watching for KEL/TEL/Credential exports.
"""

import asyncio
import logging
import socket
from pathlib import Path

from keri.app.habbing import Habery, Hab
from keri.core import coring, parsing
from keri.vdr import verifying
from keri.vdr.eventing import Tevery

from sentinel.framework.events import KELEvent, TELEvent, CredentialEvent
from sentinel.framework.registry import get_registry

logger = logging.getLogger(__name__)


class FileWatchingService:
    """
    Polling-based file watching service for KEL/TEL/Credential exports.

    Monitors export directories for .cesr files and dispatches events to
    registered handlers when files are created or modified.

    Designed for standalone applications - tracks state in memory using file mtimes.

    Example:
        service = FileWatchingService(
            export_dir="/usr/local/sentinel",
            poll_interval=2.0
        )
        await service.run()
    """

    def __init__(
        self,
        export_dir: str,
        poll_interval: float = 2.0,
        hby=None,
        rgy=None,
        db=None,
    ):
        """
        Initialize FileWatchingService.

        Args:
            export_dir: Base export directory (e.g., /usr/local/sentinel)
            poll_interval: Polling interval in seconds (default: 2.0)
            hby: Optional Habery instance for KERI operations
            rgy: Optional Regery instance for credentialing operations
            db: Optional database instance
        """
        self.export_dir = Path(export_dir)
        self.poll_interval = poll_interval
        self.hby = hby
        self.rgy = rgy
        self.tvy = Tevery(db=self.hby.db, reger=self.rgy.reger, lax=True, local=True)
        self.verifier = verifying.Verifier(hby=self.hby, reger=self.rgy.reger)
        self.db = db
        self.registry = get_registry()
        self._task = None
        self._running = False

        # Directories to watch: {event_type: directory_path}
        self.watch_dirs = {
            "kel": self.export_dir / "kel",
            "tel": self.export_dir / "tel",
            "credential": self.export_dir / "credential",
        }

    async def run(self):
        """
        Main async loop that polls for file changes.

        Algorithm:
        1. Sleep for poll_interval
        2. Scan watch directories for .cesr files
        3. Check file mtimes against last known state (in-memory)
        4. For new/modified files:
           - Read file contents
           - Extract AID from filename
           - Create event object
           - Dispatch to handlers via registry
        5. Update in-memory state with new file mtimes

        Runs until stop() is called or task is cancelled.
        """
        self._running = True
        logger.info(
            f"FileWatchingService: Starting with poll_interval={self.poll_interval}s, "
            f"watching {self.export_dir}"
        )

        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)

                # Skip if no handlers registered
                if not self.registry.get_handlers():
                    logger.debug(
                        "FileWatchingService: No handlers registered, skipping"
                    )
                    continue

                # Scan each watch directory
                for event_type, watch_dir in self.watch_dirs.items():
                    if not watch_dir.exists():
                        logger.debug(
                            f"FileWatchingService: Directory does not exist: {watch_dir}"
                        )
                        continue

                    await self._scan_directory(event_type, watch_dir)

            except asyncio.CancelledError:
                logger.info("FileWatchingService: Task cancelled")
                break
            except Exception as e:
                logger.exception(f"FileWatchingService: Error in run loop: {e}")
                # Continue despite errors

        logger.info("FileWatchingService: Stopped")

    async def _scan_directory(self, event_type: str, directory: Path):
        """
        Scan a directory for .cesr files and dispatch events for changes.

        Args:
            event_type: Event type ('kel', 'tel', 'cred')
            directory: Directory path to scan
        """
        try:
            for filepath in directory.glob("*.cesr"):
                try:
                    # Get file stats
                    stat = filepath.stat()
                    mtime = int(stat.st_mtime)

                    # Check against last known state (in-memory)
                    file_key = str(filepath)
                    last_mtime = self.db.file_state.get(keys=(file_key,))

                    if last_mtime is not None and mtime <= last_mtime.num:  # type: ignore
                        # No change
                        continue

                    # File is new or modified
                    logger.info(
                        f"FileWatchingService: Detected change - {event_type}/{filepath.name}"
                    )

                    # Read file contents
                    with open(filepath, "rb") as f:
                        data = f.read()

                    # Extract AID from filename (filename is {aid}.cesr)
                    aid = filepath.stem

                    parsing.Parser().parse(
                        ims=bytes(data),
                        kvy=self.hby.kvy,
                        tvy=self.tvy,
                        vry=self.verifier,
                        local=True,
                    )

                    # Create event object
                    event_class = {
                        "kel": KELEvent,
                        "tel": TELEvent,
                        "credential": CredentialEvent,
                    }[event_type]

                    event = event_class(
                        aid=aid,
                        filepath=str(filepath),
                        data=data,
                        timestamp=mtime,
                        hby=self.hby,
                        db=self.db,
                    )

                    # Dispatch to handlers
                    await self.registry.dispatch(event_type, event)

                    # Update in-memory state
                    self.db.file_state.pin(
                        keys=(file_key,), val=coring.Number(num=mtime)
                    )

                except Exception as e:
                    logger.exception(
                        f"FileWatchingService: Error processing {filepath}: {e}"
                    )
                    continue

        except Exception as e:
            logger.exception(f"FileWatchingService: Error scanning {directory}: {e}")

    def start(self):
        """
        Start the service as an asyncio task.

        Returns:
            The asyncio Task running the service
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    def stop(self):
        """
        Stop the service task.

        Sets the running flag to False and cancels the task if still running.
        """
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()


class LocalWatcherConnector:
    """
    Local watcher client that sends watch requests to sentinel via unix domain socket.

    Connects to a local sentinel watcher service and sends KERI rpy (reply) messages
    to add AIDs to the watch list.
    """

    def __init__(self, hby: Habery, hab: Hab, watcher: str):
        """
        Initialize LocalWatcher with KERI context.

        Parameters:
            hby: Habery instance for KERI keystore management
            hab: Hab instance representing the server's identity
            watcher: The AID (Autonomic Identifier) of the watcher service

        """
        self.hby = hby
        self.hab = hab
        self.watcher = watcher

        # Socket path based on server's AID prefix
        self.socket_path = f"/tmp/sentinel_{watcher}.sock"

    def watch(self, aid: str, oobi) -> bool:
        """
        Send watch request for an AID to local sentinel.

        Creates a KERI rpy (reply) message with route '/watcher/{aid}/add'
        and sends it to the sentinel watcher via unix domain socket.

        Parameters:
            aid: The AID (Autonomic Identifier) to watch
            oobi: Out-of-band introduction for the AID

        Returns:
            True if message sent successfully, False otherwise

        Raises:
            ConnectionError: If unable to connect to sentinel socket
            OSError: If socket communication fails
        """
        # Build the route with the AID
        route = f"/watcher/{self.watcher}/add"
        data = dict(cid=self.hab.pre, oid=aid)
        if oobi:
            data["oobi"] = oobi

        msg = self.hab.reply(route=route, data=data)
        self.hab.psr.parseOne(ims=bytes(msg))

        # Create KERI rpy message structure
        # Based on KERI message format with route and sender info
        # Send via unix domain socket
        try:
            # Create unix domain socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

            try:
                # Connect to sentinel socket
                sock.connect(self.socket_path)

                # Send the message
                sock.sendall(msg)

                return True

            finally:
                # Always close the socket
                sock.close()

        except FileNotFoundError:
            raise ConnectionError(
                f"Sentinel socket not found at {self.socket_path}. "
                "Is the sentinel service running?"
            )
        except (ConnectionRefusedError, socket.error) as e:
            raise ConnectionError(
                f"Failed to connect to sentinel at {self.socket_path}: {e}"
            )
