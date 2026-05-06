# -*- encoding: utf-8 -*-
"""
locksmith.core.watching module

Functions and services for managing healthKERI account watchers
"""
import asyncio
import random
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from kept.hk.essring import APIClient
from keri import help, kering
from keri.app.connecting import Organizer
from keri.app.habbing import Habery
from keri.core import coring

from sentinel.core import remoting

logger = help.ogler.getLogger()


async def fetch_account_watched(
        essr,
        page: int = 0,
        page_size: int = 10,
        filter_term: Optional[str] = None,
        order: Optional[list] = None
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
            data['success'] = True
            return data
        else:
            return {
                'success': False,
                'error': f"API error: {response.status_code if response else 'No response'}"
            }

    except Exception as e:
        logger.error(f"Error fetching watched identifiers: {e}")
        return {'success': False, 'error': str(e)}


async def delete_account_watcher(
        essr,
        eid: str
) -> Dict[str, Any]:
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
        response = await essr.request(
            path=f"/watched/{eid}",
            method="DELETE"
        )

        if response and response.status_code == 204:
            return {'success': True}
        else:
            error_msg = "Unknown error"
            if response:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('description', str(response.status_code))
                except Exception:
                    error_msg = f"Status {response.status_code}"
            return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error deleting account watcher: {e}")
        return {'success': False, 'error': str(e)}

async def add_watched_identifier(hby, essr, watched_aid: str, alias: str) -> dict:

    try:
        # Verify watched identifier is in kevers
        if watched_aid not in hby.kevers:
            raise ValueError(f"Watched identifier {watched_aid} not found in KERI database")

        kever = hby.kevers[watched_aid]

        # Verify watched identifier has witnesses
        if not kever.wits:
            raise ValueError(f"Watched identifier {watched_aid} does not have witnesses")

        wit = random.choice(kever.wits)
        urls = {keys[1]: loc.url for keys, loc in
                hby.db.locs.getItemIter(keys=(wit,)) if loc.url}
        if not urls:
            raise ValueError(f"unable to query witness {wit}, no http endpoint")

        url = urls[kering.Schemes.https] if kering.Schemes.https in urls else urls[kering.Schemes.http]
        oobi = f"{url.rstrip("/")}/oobi/{kever.serder.pre}/witness"

        doc = {'name': alias, 'aid': watched_aid, 'oobi': oobi}

        # APIClient.request is the async method
        response = await essr.request(
            path=f"/watched",
            method="POST",
            json=doc
        )

        if response and response.status_code in (204, 200, 201):
            return {'success': True}
        else:
            error_msg = "Unknown error"
            if response:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('description', str(response.status_code))
                except Exception:
                    error_msg = f"Status {response.status_code}"
            return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.error(f"Error deleting account watcher: {e}")
        return {'success': False, 'error': str(e)}


class WatchedAdjudicationPoller:
    """
    Background asyncio task that polls for adjudications of watched identifiers.

    Checks the ESSR service for new adjudications after the last poll time,
    compares remote sequence numbers with local state, and creates notifications
    when watched identifiers are out of sync (local state is behind remote).

    The poll datetime is stored in the healthKERI database's watched_poll table.
    """

    def __init__(self, hby: Habery, essr: APIClient, db, poll_interval: float = 30.0, check_interval: float = 30.0):
        """
        Initialize the WatchedAdjudicationPoller.

        Args:
            hby: Habery instance for managing healthKERI accounts
            essr: APIClient instance for interacting with healthKERI API
            db: Database instance with watched_poll table
            poll_interval: Polling interval in seconds (default: 30 seconds)
            check_interval: Timer interval for checking adjudications loop (default: 0.5 seconds)
        """
        self.hby = hby
        self.essr = essr
        self.db = db
        self.poll_interval = poll_interval
        self.check_interval = check_interval
        self.query_done = True
        self._task = None
        self._running = False

    async def run(self):
        """
        Main asyncio loop that polls for adjudications on a timer.

        This method:
        1. Runs in an infinite loop with check_interval sleep
        2. Reads the last poll datetime from watched_poll database
        3. Queries ESSR for adjudications after that datetime
        4. For each adjudication, checks if local state is out of sync
        5. Syncs out-of-sync watched identifiers
        6. Updates the poll datetime in the database

        This method should be run as an asyncio task.
        """
        self._running = True
        logger.info(f"WatchedAdjudicationPoller: Starting with check_interval={self.check_interval}s")

        while self._running:
            try:
                # Sleep for check_interval before polling
                await asyncio.sleep(self.check_interval)

                # Check if we have necessary resources
                if not self.db:
                    logger.debug("WatchedAdjudicationPoller: No ESSR or DB available, skipping poll")
                    continue

                if not self.db.watched_poll:
                    logger.debug("WatchedAdjudicationPoller: watched_poll database not available")
                    continue

                # Skip if previous query still running
                if not self.query_done:
                    logger.debug("WatchedAdjudicationPoller: Previous query still running, skipping")
                    continue

                # Get last poll datetime from database
                last_poll_dater = self.db.watched_poll.get(keys=("last",))

                if last_poll_dater:
                    # Convert Dater to datetime
                    last_poll_dt = datetime.fromisoformat(last_poll_dater.dts)
                    logger.debug(f"WatchedAdjudicationPoller: Last poll time: {last_poll_dt}")
                else:
                    # First poll - use a datetime from 1 day ago
                    last_poll_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                    logger.debug(f"WatchedAdjudicationPoller: First poll, using {last_poll_dt}")

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
            logger.debug(f"WatchedAdjudicationPoller: Query response status: {response.status_code} - {response.text}")
            if not response or response.status_code != 200:
                logger.error(
                    f"WatchedAdjudicationPoller: API error: "
                    f"{response.status_code if response else 'No response'}"
                )
                return

            data = response.json()
            adjudications = data.get('adjudications', [])

            if not adjudications:
                logger.info("WatchedAdjudicationPoller: No new adjudications")
            else:
                logger.info(f"WatchedAdjudicationPoller: Found {len(adjudications)} adjudications")

            org = Organizer(hby=self.hby)

            # Process each adjudication
            for adj in adjudications:
                try:
                    watched_aid = adj.get('watched_aid')
                    remote_sn = int(adj.get('sn', 0))
                    remote_dig = adj.get('dig')

                    if not watched_aid:
                        logger.warning("WatchedAdjudicationPoller: Adjudication missing aid, skipping")
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
                    watched_name = contact.get('alias') if contact else watched_aid

                    local_sn = kever.sner.num

                    # Check if out of sync (local behind remote)
                    if local_sn < remote_sn:
                        logger.debug(
                            f"WatchedAdjudicationPoller: {watched_name} is out of sync - "
                            f"local SN {local_sn} < remote SN {remote_sn}"
                        )

                        await remoting.sync_watched_identifier(self.hby, self.essr, kever.pre)

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
