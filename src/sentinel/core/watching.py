# -*- encoding: utf-8 -*-
"""
sentinel.core.watching module

Functions and services for managing healthKERI account watchers
"""

import asyncio
import httpx
import os
import random
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set

from kept.hk.essring import APIClient
from keri import help, kering
from keri.app.connecting import Organizer
from keri.app.habbing import Habery
from keri.core import coring, parsing
from keri.vdr.credentialing import Regery

from sentinel.core import filing, remoting
from sentinel.core.credentialing import CredentialLoader, SaaSCredentialLoader

logger = help.ogler.getLogger()


async def fetch_account_watched(
    essr,
    page: int = 0,
    page_size: int = 10,
    filter_term: Optional[str] = None,
    order: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Fetch account watchers from the healthKERI API.

    Args:
        hby: Habery instance for managing healthKERI accounts
        essr: APIClient instance for interacting with healthKERI API
        page: Page number (0-indexed)
        page_size: Number of items per page
        filter_term: Optional filter/search term
        order: Optional list of sort orders (e.g., ['+name', '-eid'])

    Returns:
        API response with watchers data
    """
    try:
        # Build query parameters
        params = [f"page={page}", f"page_size={page_size}"]

        if filter_term:
            params.append(f"filter={urllib.parse.quote(filter_term)}")

        if order:
            for o in order:
                params.append(f"order={urllib.parse.quote(o)}")

        path = f"/watched?{'&'.join(params)}"

        # Make async request - APIClient.request is the async method
        response = await essr.request(path=path, method="GET")
        if response and response.status_code == 200:
            data = response.json()
            data["success"] = True
            return data
        else:
            return {
                "success": False,
                "error": f"API error: {response.status_code if response else 'No response'}",
            }

    except Exception as e:
        logger.error(f"Error fetching watched identifiers: {e}")
        return {"success": False, "error": str(e)}


async def delete_account_watcher(essr, eid: str) -> Dict[str, Any]:
    """
    Delete a watcher from the healthKERI account.

    Args:
        essr: ESSR connection instance
        eid: ID of the watcher to delete

    Returns:
        Dict with 'success' and optional 'error'
    """

    try:
        # APIClient.request is the async method
        response = await essr.request(path=f"/watched/{eid}", method="DELETE")

        if response and response.status_code == 204:
            return {"success": True}
        else:
            error_msg = "Unknown error"
            if response:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("description", str(response.status_code))
                except Exception:
                    error_msg = f"Status {response.status_code}"
            return {"success": False, "error": error_msg}

    except Exception as e:
        logger.error(f"Error deleting account watcher: {e}")
        return {"success": False, "error": str(e)}


async def resolve_identifier_kel(
    hby,
    aid: str,
    registrar_url: Optional[str] = None,
    export_dir: Optional[str] = None,
) -> dict:
    """
    Resolve and load KEL for an identifier from registrar if not already in kevers.

    Args:
        hby: Habery instance
        aid: Identifier to resolve
        registrar_url: URL of registrar to fetch OOBI from
        export_dir: Directory to export KEL to after loading

    Returns:
        Dict with 'success' and optional 'error'
    """
    try:
        # Check if identifier already in kevers
        if aid in hby.kevers:
            logger.debug(f"Identifier {aid} already in kevers, no resolution needed")
            return {"success": True}

        # If no registrar_url, cannot resolve
        if not registrar_url:
            logger.error(
                f"Identifier {aid} not in kevers and no registrar_url provided"
            )
            return {
                "success": False,
                "error": "Identifier not found and no registrar URL available",
            }

        logger.info(
            f"Identifier {aid} not in kevers, attempting OOBI resolution from registrar"
        )

        # Fetch OOBI from registrar
        oobi_url = f"{registrar_url.rstrip('/')}/oobi/{aid}"
        logger.info(f"Fetching OOBI from {oobi_url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(oobi_url)

                if response.status_code == 404:
                    logger.error(f"OOBI not found for {aid} at registrar")
                    return {
                        "success": False,
                        "error": f"Identifier {aid} not found at registrar",
                    }

                if response.status_code != 200:
                    logger.error(
                        f"Failed to fetch OOBI for {aid}: status {response.status_code}"
                    )
                    return {
                        "success": False,
                        "error": f"Failed to fetch OOBI (status {response.status_code})",
                    }

                oobi_data = response.content
                logger.debug(
                    f"Successfully fetched OOBI for {aid} ({len(oobi_data)} bytes)"
                )

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching OOBI for {aid}: {e}")
                return {
                    "success": False,
                    "error": "Network error fetching OOBI from registrar",
                }

        # Parse OOBI to load KEL
        logger.debug(f"Parsing OOBI data for {aid}")
        hby.psr.parse(oobi_data)
        hby.kvy.processEscrows()
        if hasattr(hby, "rvy") and hby.rvy:
            hby.rvy.processEscrowReply()

        # Verify KEL loaded successfully
        if aid not in hby.kevers:
            logger.error(f"Failed to load KEL for {aid} after OOBI resolution")
            return {
                "success": False,
                "error": f"Identifier {aid} could not be resolved",
            }

        logger.info(f"Successfully resolved OOBI for {aid}")

        # Export KEL to filesystem if export_dir provided
        if export_dir:
            try:
                success = await filing.export_kel(
                    hby=hby, aid=aid, export_dir=export_dir
                )
                if success:
                    logger.info(f"Successfully exported KEL for {aid}")
                else:
                    logger.warning(f"Failed to export KEL for {aid}")
            except Exception as e:
                logger.error(f"Error exporting KEL for {aid}: {e}")
                # Continue - export failure shouldn't block resolution

        return {"success": True}

    except Exception as e:
        logger.error(f"Error resolving identifier KEL for {aid}: {e}")
        return {"success": False, "error": str(e)}


async def add_watched_identifier(
    hby,
    essr,
    watched_aid: str,
    alias: str,
    registrar_url: Optional[str] = None,
    export_dir: Optional[str] = None,
    _retry_count: int = 0,
) -> dict:
    try:
        # Guard against infinite recursion
        MAX_RETRY_COUNT = 1
        if _retry_count > MAX_RETRY_COUNT:
            logger.error(f"Maximum retry count exceeded for {watched_aid}")
            raise ValueError(
                f"Failed to add watched identifier {watched_aid} after retry"
            )

        # Verify watched identifier is in kevers
        if watched_aid not in hby.kevers:
            # Attempt OOBI resolution if this is first try and registrar_url provided
            if _retry_count == 0 and registrar_url:
                result = await resolve_identifier_kel(
                    hby=hby,
                    aid=watched_aid,
                    registrar_url=registrar_url,
                    export_dir=export_dir,
                )

                if not result.get("success"):
                    raise ValueError(
                        result.get("error", "Failed to resolve identifier")
                    )

                # Retry with incremented counter
                return await add_watched_identifier(
                    hby=hby,
                    essr=essr,
                    watched_aid=watched_aid,
                    alias=alias,
                    registrar_url=registrar_url,
                    export_dir=export_dir,
                    _retry_count=_retry_count + 1,
                )
            else:
                # No registrar_url or already retried
                raise ValueError(
                    f"Watched identifier {watched_aid} not found in KERI database"
                )

        kever = hby.kevers[watched_aid]

        # Verify watched identifier has witnesses
        if not kever.wits:
            raise ValueError(
                f"Watched identifier {watched_aid} does not have witnesses"
            )

        wit = random.choice(kever.wits)
        urls = {
            keys[1]: loc.url
            for keys, loc in hby.db.locs.getItemIter(keys=(wit,))
            if loc.url
        }
        if not urls:
            raise ValueError(f"unable to query witness {wit}, no http endpoint")

        url = (
            urls[kering.Schemes.https]
            if kering.Schemes.https in urls
            else urls[kering.Schemes.http]
        )
        oobi = f"{url.rstrip("/")}/oobi/{kever.serder.pre}/witness"

        doc = {"name": alias, "aid": watched_aid, "oobi": oobi}

        # APIClient.request is the async method
        response = await essr.request(path="/watched", method="POST", json=doc)

        if response and response.status_code in (204, 200, 201):
            return {"success": True}
        else:
            error_msg = "Unknown error"
            if response:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("description", str(response.status_code))
                except Exception:
                    error_msg = f"Status {response.status_code}"
            return {"success": False, "error": error_msg}

    except Exception as e:
        logger.error(f"Error adding watched identifier: {e}")
        return {"success": False, "error": str(e)}


class WatchedAdjudicationPoller:
    """
    Background asyncio task that polls for adjudications of watched identifiers.

    Checks the ESSR service for new adjudications after the last poll time,
    compares remote sequence numbers with local state, and creates notifications
    when watched identifiers are out of sync (local state is behind remote).

    The poll datetime is stored in the healthKERI database's watched_poll table.
    """

    def __init__(
        self,
        hby: Habery,
        rgy: Regery,
        essr: APIClient,
        db,
        poll_interval: float = 30.0,
        export_dir: str = "/usr/local/sentinel",
        registrar_url: Optional[str] = None,
        saas_loader: Optional[SaaSCredentialLoader] = None,
    ):
        """
        Initialize the WatchedAdjudicationPoller.

        Args:
            hby: Habery instance for managing healthKERI accounts
            essr: APIClient instance for interacting with healthKERI API
            db: Database instance with watched_poll table
            poll_interval: Polling interval in seconds (default: 30 seconds)
            export_dir: Directory for exporting CESR files (default: /usr/local/sentinel)
            registrar_url: URL for credential registrar API (local mode, default: None)
            saas_loader: SaaSCredentialLoader for SaaS mode (takes priority over registrar_url)

        """
        self.hby = hby
        self.essr = essr
        if saas_loader is not None:
            self.credential_loader = saas_loader
        elif registrar_url:
            self.credential_loader = CredentialLoader(hby, self.essr.hab, rgy, export_dir, registrar_url)
        else:
            self.credential_loader = None

        self.db = db
        self.poll_interval = poll_interval
        self.export_dir = export_dir

        self.query_done = True
        self._task = None
        self._running = False

    async def run(self):
        """
        Main asyncio loop that polls for adjudications on a timer.

        This method:
        1. Runs in an infinite loop with poll_interval sleep
        2. Reads the last poll datetime from watched_poll database
        3. Queries ESSR for adjudications after that datetime
        4. For each adjudication, checks if local state is out of sync
        5. Syncs out-of-sync watched identifiers
        6. Updates the poll datetime in the database

        This method should be run as an asyncio task.
        """
        self._running = True
        logger.info(
            f"WatchedAdjudicationPoller: Starting with poll_interval={self.poll_interval}s"
        )

        while self._running:
            try:
                # Sleep for poll_interval before polling
                await asyncio.sleep(self.poll_interval)

                # Check if we have necessary resources
                if not self.db:
                    logger.debug(
                        "WatchedAdjudicationPoller: No ESSR or DB available, skipping poll"
                    )
                    continue

                if not self.db.watched_poll:
                    logger.debug(
                        "WatchedAdjudicationPoller: watched_poll database not available"
                    )
                    continue

                # Skip if previous query still running
                if not self.query_done:
                    logger.debug(
                        "WatchedAdjudicationPoller: Previous query still running, skipping"
                    )
                    continue

                # Get last poll datetime from database
                last_poll_dater = self.db.watched_poll.get(keys=("last",))

                if last_poll_dater:
                    # Convert Dater to datetime
                    last_poll_dt = datetime.fromisoformat(last_poll_dater.dts)
                    logger.debug(
                        f"WatchedAdjudicationPoller: Last poll time: {last_poll_dt}"
                    )
                else:
                    # First poll - use a datetime from 1 day ago
                    last_poll_dt = datetime.now(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    logger.debug(
                        f"WatchedAdjudicationPoller: First poll, using {last_poll_dt}"
                    )

                # Query ESSR for adjudications after last poll time
                # Format datetime for API query (ISO 8601)
                after_param = last_poll_dt.isoformat()
                path = f"/adjudications?date={urllib.parse.quote(after_param)}"

                logger.debug(f"WatchedAdjudicationPoller: Querying {path}")

                # Poll adjudications
                await self._async_poll_adjudications(path)

            except asyncio.CancelledError:
                logger.info("WatchedAdjudicationPoller: Task cancelled")
                break
            except Exception as e:
                logger.exception(f"WatchedAdjudicationPoller: Error in run loop: {e}")
                # Continue running despite errors

        logger.info("WatchedAdjudicationPoller: Stopped")

    async def _async_poll_adjudications(self, path: str):
        """
        Async helper to poll adjudications and sync watched identifiers.

        Args:
            path: API path to query
        """
        self.query_done = False
        try:
            response = await self.essr.request(path=path, method="GET")
            logger.debug(
                f"WatchedAdjudicationPoller: Query response status: {response.status_code} - {response.text}"
            )
            if not response or response.status_code != 200:
                logger.error(
                    f"WatchedAdjudicationPoller: API error: "
                    f"{response.status_code if response else 'No response'}"
                )
                return

            data = response.json()
            adjudications = data.get("adjudications", [])

            if not adjudications:
                logger.info("WatchedAdjudicationPoller: No new adjudications")
            else:
                logger.info(
                    f"WatchedAdjudicationPoller: Found {len(adjudications)} adjudications"
                )

            org = Organizer(hby=self.hby)

            # Process each adjudication
            for adj in adjudications:
                try:
                    watched_aid = adj.get("watched_aid")
                    remote_sn = int(adj.get("sn", 0))

                    if not watched_aid:
                        logger.warning(
                            "WatchedAdjudicationPoller: Adjudication missing aid, skipping"
                        )
                        continue

                    # Check local state
                    kever = self.hby.kevers.get(watched_aid)

                    if not kever:
                        logger.debug(
                            f"WatchedAdjudicationPoller: Watched identifier {watched_aid} "
                            f"not found locally, skipping"
                        )
                        continue

                    contact = org.get(pre=watched_aid)
                    watched_name = contact.get("alias") if contact else watched_aid

                    local_sn = kever.sner.num

                    # Check if out of sync (local behind remote)
                    if local_sn < remote_sn:
                        logger.debug(
                            f"WatchedAdjudicationPoller: {watched_name} is out of sync - "
                            f"local SN {local_sn} < remote SN {remote_sn}"
                        )

                        await remoting.sync_watched_identifier(
                            self.hby, self.essr, kever.pre
                        )

                        # Export KEL to filesystem
                        try:
                            await filing.export_kel(
                                hby=self.hby, aid=kever.pre, export_dir=self.export_dir
                            )
                        except Exception as e:
                            logger.error(
                                f"WatchedAdjudicationPoller: Failed to export KEL for {watched_name}: {e}"
                            )

                        # Trigger credential search if appropriate
                        if self.credential_loader:
                            asyncio.create_task(
                                self.credential_loader.search_for_credentials(
                                    watched_aid, remote_sn
                                )
                            )

                    else:
                        logger.debug(
                            f"WatchedAdjudicationPoller: {watched_name} is in sync - "
                            f"local SN {local_sn} >= remote SN {remote_sn}"
                        )

                except Exception as e:
                    logger.exception(
                        f"WatchedAdjudicationPoller: Error processing adjudication: {e}"
                    )
                    continue

            # Update last poll datetime to now
            now = datetime.now(timezone.utc)
            now_dater = coring.Dater(dts=now.isoformat())
            self.db.watched_poll.pin(keys=("last",), val=now_dater)
            logger.debug(f"WatchedAdjudicationPoller: Updated last poll time to {now}")

        except Exception as e:
            logger.exception(f"WatchedAdjudicationPoller: Error in async poll: {e}")
        finally:
            self.query_done = True

    def start(self):
        """
        Start the poller as an asyncio task.

        Returns:
            The asyncio Task object
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    def stop(self):
        """
        Stop the poller task.
        """
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()


class ObvsSocketListener:
    """
    Asyncio-based Unix Domain Socket listener that monitors new obvs entries.

    Listens on a Unix Domain Socket for connections. When a connection is received,
    reads all data from the connection, then checks hby.db.obvs for new entries
    (datetime > last_check) and calls add_watched_identifier for each new entry.
    """

    def __init__(
        self,
        hby: Habery,
        essr: APIClient,
        db,
        socket_path: str,
        poll_interval: float = 0.5,
        registrar_url: Optional[str] = None,
        export_dir: Optional[str] = None,
    ):
        """
        Initialize the ObvsSocketListener.

        Args:
            hby: Habery instance for managing healthKERI accounts
            essr: APIClient instance for interacting with healthKERI API
            db: Database instance with watched_poll table
            socket_path: Path to Unix Domain Socket (e.g., /tmp/sentinel_name.sock)
            poll_interval: Timer interval for checking connections (default: 0.5 seconds)
            registrar_url: URL for credential registrar API (default: None)
            export_dir: Directory for exporting CESR files (default: None)
        """
        self.hby = hby
        self.psr = parsing.Parser(kvy=self.hby.kvy, rvy=self.hby.rvy, local=True)
        self.essr = essr
        self.db = db
        self.socket_path = socket_path
        self.poll_interval = poll_interval
        self.registrar_url = registrar_url
        self.export_dir = export_dir
        self._server = None
        self._task = None
        self._running = False
        self._connection_tasks: Set[asyncio.Task] = set()

    async def run(self):
        """
        Main asyncio loop that runs the Unix Domain Socket server.

        This method:
        1. Removes existing socket file if present
        2. Creates Unix Domain Socket server
        3. Accepts connections and processes them
        4. Handles cleanup on shutdown
        """
        self._running = True
        logger.info(f"ObvsSocketListener: Starting server on {self.socket_path}")

        try:
            # Remove existing socket file if present
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
                logger.debug(
                    f"ObvsSocketListener: Removed existing socket file {self.socket_path}"
                )

            # Create Unix Domain Socket server
            self._server = await asyncio.start_unix_server(
                self._handle_connection, path=self.socket_path
            )

            logger.info(f"ObvsSocketListener: Server listening on {self.socket_path}")

            # Run server loop
            while self._running:
                await asyncio.sleep(self.poll_interval)

                # Clean up finished connection tasks
                self._connection_tasks = {
                    task for task in self._connection_tasks if not task.done()
                }

        except asyncio.CancelledError:
            logger.info("ObvsSocketListener: Task cancelled")
        except Exception as e:
            logger.exception(f"ObvsSocketListener: Error in run loop: {e}")
        finally:
            await self._cleanup()

        logger.info("ObvsSocketListener: Stopped")

    async def _cleanup(self):
        """
        Clean up server resources and socket file.
        """
        try:
            logger.info("ObvsSocketListener: Cleaning up...")

            # Close server
            if self._server:
                self._server.close()
                await self._server.wait_closed()
                logger.debug("ObvsSocketListener: Server closed")

            # Remove socket file
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
                logger.debug(
                    f"ObvsSocketListener: Removed socket file {self.socket_path}"
                )

            # Cancel all connection tasks
            if self._connection_tasks:
                logger.debug(
                    f"ObvsSocketListener: Cancelling {len(self._connection_tasks)} connection tasks"
                )
                for task in self._connection_tasks:
                    task.cancel()

                # Wait for all tasks to complete
                await asyncio.gather(*self._connection_tasks, return_exceptions=True)

        except Exception as e:
            logger.exception(f"ObvsSocketListener: Error during cleanup: {e}")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """
        Handle a new connection by creating a task for it.

        Args:
            reader: StreamReader for reading from the connection
            writer: StreamWriter for writing to the connection
        """
        task = asyncio.create_task(self._process_connection(reader, writer))
        self._connection_tasks.add(task)

    async def _process_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """
        Process a single connection: read data and check obvs.

        Args:
            reader: StreamReader for reading from the connection
            writer: StreamWriter for writing to the connection
        """
        peer = writer.get_extra_info("peername")
        logger.info(f"ObvsSocketListener: New connection from {peer}")

        try:
            # Read all data from connection
            data = bytearray()
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                data.extend(chunk)

            logger.debug(f"ObvsSocketListener: Received {len(data)} bytes from {peer}")

            # Check and add new obvs entries
            self.psr.parseOne(data)
            await self._check_and_add_obvs()

        except Exception as e:
            logger.exception(
                f"ObvsSocketListener: Error processing connection from {peer}: {e}"
            )
        finally:
            try:
                writer.close()
                await writer.wait_closed()
                logger.info(f"ObvsSocketListener: Connection from {peer} closed")
            except Exception as e:
                logger.exception(f"ObvsSocketListener: Error closing connection: {e}")

    async def _check_and_add_obvs(self):
        """
        Check hby.db.obvs for new entries and add them as watched identifiers.

        Filters obvs entries based on timestamp (datetime > last_check) and calls
        add_watched_identifier for each new entry.
        """
        try:
            # Check if we have necessary resources
            if not self.db:
                logger.warning(
                    "ObvsSocketListener: No DB available, skipping obvs check"
                )
                return

            if not self.db.watched_poll:
                logger.warning(
                    "ObvsSocketListener: watched_poll database not available"
                )
                return

            if not hasattr(self.hby.db, "obvs"):
                logger.warning("ObvsSocketListener: obvs database not available")
                return

            # Get last check timestamp from database
            last_check_dater = self.db.watched_poll.get(keys=("obvs_last",))

            if last_check_dater:
                last_check_dt = datetime.fromisoformat(last_check_dater.dts)
                logger.debug(f"ObvsSocketListener: Last check time: {last_check_dt}")
            else:
                # First check - use epoch
                last_check_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
                logger.debug(
                    f"ObvsSocketListener: First check, using epoch {last_check_dt}"
                )

            # Iterate through obvs entries
            new_count = 0
            success_count = 0
            error_count = 0

            for (cid, aid, oid), observed in self.hby.db.obvs.getItemIter():
                try:
                    # Check if entry has datetime and is newer than last check
                    if not hasattr(observed, "datetime") or not observed.datetime:
                        logger.debug(
                            f"ObvsSocketListener: Skipping obvs entry without datetime - oid={oid}"
                        )
                        continue

                    observed_dt = datetime.fromisoformat(observed.datetime)

                    if observed_dt > last_check_dt:
                        new_count += 1
                        logger.info(
                            f"ObvsSocketListener: New obvs entry - cid={cid}, aid={aid}, oid={oid}, "
                            f"name={getattr(observed, 'name', 'N/A')}, datetime={observed.datetime}"
                        )

                        # Add watched identifier
                        alias = getattr(observed, "name", oid)
                        result = await add_watched_identifier(
                            hby=self.hby,
                            essr=self.essr,
                            watched_aid=oid,
                            alias=alias,  # type: ignore
                            registrar_url=self.registrar_url,
                            export_dir=self.export_dir,
                        )

                        if result.get("success"):
                            success_count += 1
                            logger.info(
                                f"ObvsSocketListener: Successfully added watched identifier - "
                                f"oid={oid}, alias={alias}"
                            )
                        else:
                            error_count += 1
                            error_msg = result.get("error", "Unknown error")
                            logger.error(
                                f"ObvsSocketListener: Failed to add watched identifier - "
                                f"oid={oid}, alias={alias}, error={error_msg}"
                            )

                except Exception as e:
                    error_count += 1
                    logger.exception(
                        f"ObvsSocketListener: Error processing obvs entry (oid={oid}): {e}"
                    )
                    continue

            # Update last check timestamp to now
            now = datetime.now(timezone.utc)
            now_dater = coring.Dater(dts=now.isoformat())
            self.db.watched_poll.pin(keys=("obvs_last",), val=now_dater)
            logger.debug(f"ObvsSocketListener: Updated last check time to {now}")

            logger.info(
                f"ObvsSocketListener: Processed {new_count} new obvs entries - "
                f"success={success_count}, errors={error_count}"
            )

        except Exception as e:
            logger.exception(f"ObvsSocketListener: Error in _check_and_add_obvs: {e}")

    def start(self):
        """
        Start the socket listener as an asyncio task.

        Returns:
            The asyncio Task object
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    def stop(self):
        """
        Stop the socket listener task.
        """
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
