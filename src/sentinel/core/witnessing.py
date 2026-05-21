# -*- encoding: utf-8 -*-

"""
Sentinel
sentinel.core.witnessing package

"""

import asyncio
import os
from datetime import datetime, timezone, timedelta
import random
from typing import Optional, Set

import httpx
from hio.help import decking
from keri import help
from keri.app.habbing import Habery
from keri.core import routing, eventing, parsing, coring
from keri.help import helping
from keri.peer import exchanging
from keri.vdr import verifying
from keri.vdr.eventing import Tevery

from sentinel.core import querying, filing
from sentinel.core.credentialing import CredentialLoader
from sentinel.db.basing import States, WitnessState, WitnessQuery

logger = help.ogler.getLogger()

WATCHER_CAPACITY = 10


class Watcher:
    """Instance represents a provisioned Watcher for a single AID controller

    Main entity for performing watcher functionality on behalf of its controller represented by aid

    """

    def __init__(
        self,
        db,
        hby,
        hab,
        rgy,
        export_dir: str = "/usr/local/sentinel",
        registrar_url: str | None = None,
    ):
        """Create new watcher, or loaded from database on startup

        Parameters:
            db (Baser): database instance for watcher specific data
            hby (Habery): key state database environment for this watcher instance
            hab (Hab): Habitat of the non-transferable AID for this watcher
            rgy (Registry): Registry instance for managing credential registry operations
            export_dir (str): Directory for exporting CESR files
            registrar_url (str | None): URL for credential registrar
        """
        self.db = db
        self.hby = hby
        self.hab = hab
        self.rgy = rgy
        self.export_dir = export_dir
        self.cid = self.hab.pre
        self.registrar_url = registrar_url

        # KERI components expect a Deck-like object for cues
        # We keep using Deck for compatibility with KERI library
        self.cues = decking.Deck()

        self.rtr = routing.Router()
        self.rvy = routing.Revery(
            db=self.hby.db, rtr=self.rtr, cues=self.cues, lax=True, local=False
        )

        #  needs unique kevery with ims per remoter connnection
        self.kvy = eventing.Kevery(
            db=self.hby.db,
            cues=self.cues,
            rvy=self.rvy,
            lax=True,
            local=False,
            direct=False,
        )
        self.kvy.registerReplyRoutes(self.rtr)

        self.verifier = verifying.Verifier(hby=self.hby, reger=self.rgy.reger)
        self.tvy = Tevery(
            reger=self.verifier.reger,
            db=self.hby.db,
            rvy=self.rvy,
            lax=True,
            local=False,
            cues=self.cues,
        )
        self.tvy.registerReplyRoutes(self.rtr)

        self.exc = exchanging.Exchanger(hby=self.hby, handlers=[])

        self.psr = parsing.Parser(
            framed=True,
            kvy=self.kvy,
            tvy=self.tvy,
            exc=self.exc,
            rvy=self.rvy,
            vry=self.verifier,
        )

        self.watched_identifiers = set()
        for (_, _, oid), _ in self.hby.db.obvs.getItemIter(
            keys=(
                self.cid,
                self.hab.pre,
            )
        ):
            print(f"Adding {oid}")
            self.watched_identifiers.add(oid)

        # Background workers
        self.escrower: Optional[Escrower] = None
        self.sentinel_launcher: Optional[SentinelLauncher] = None
        self._running = False
        self._tasks = []

    def start(self):
        """Start background workers"""
        if self._running:
            return self._tasks

        self._running = True

        # Create and start background workers
        self.escrower = Escrower(kvy=self.kvy, rvy=self.rvy, tvy=self.tvy, exc=self.exc)
        self.sentinel_launcher = SentinelLauncher(
            db=self.db,
            hby=self.hby,
            hab=self.hab,
            rgy=self.rgy,
            cid=self.cid,
            export_dir=self.export_dir,
            registrar_url=self.registrar_url,
        )

        escrow_task = asyncio.create_task(self.escrower.run())
        sentinel_task = asyncio.create_task(self.sentinel_launcher.run())

        self._tasks = [escrow_task, sentinel_task]
        return self._tasks

    def stop(self):
        """Stop background workers and cleanup"""
        self._running = False

        if self.escrower:
            self.escrower.stop()
        if self.sentinel_launcher:
            self.sentinel_launcher.stop()

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        self._tasks = []

    @property
    def watched_count(self):
        return len(self.watched_identifiers)

    def watch(self, aid):
        """Watch an AID for changes"""
        if aid not in self.watched_identifiers:
            data = dict(cid=self.hab.pre, oid=aid)
            route = f"/watcher/{self.hab.pre}/add"
            msg = self.hab.reply(route=route, data=data)
            self.hab.psr.parseOne(ims=bytes(msg))

            self.watched_identifiers.add(aid)


class SentinelLauncher:
    """Background worker to process watched AIDs periodically"""

    WATCHERRETRY = 30
    CONTROLLERRETRY = 60

    def __init__(
        self,
        db,
        hby,
        hab,
        rgy,
        cid,
        export_dir: str = "/usr/local/sentinel",
        registrar_url: str | None = None,
    ):
        """Create watched processor launcher

        Parameters:
            db(Baser): Watcher op net database environment
            hby (Habery): key state database environment
            hab (Hab): Habitat of the non-transferable AID for this watcher
            rgy (Registry): Registry instance for credential management
            cid (str): qb64 of controller of the watcher for this sentinel
            export_dir (str): Directory for exporting CESR files
            registrar_url (str): URL for credential registrar

        """
        self.db = db
        self.hab = hab
        self.hby = hby
        self.rgy = rgy
        self.cid = cid
        self.export_dir = export_dir
        self.registrar_url = registrar_url
        self.sentinels = dict()
        self._running = False
        self._interval = 1.0  # Check every second

    async def run(self):
        """Main loop to process watched AIDs"""
        self._running = True

        while self._running:
            try:
                await self.watch_watched()

                # Clean up completed sentinels
                for wid, sentinel in list(self.sentinels.items()):
                    if sentinel.done:
                        del self.sentinels[wid]

                await asyncio.sleep(self._interval)
            except Exception as e:
                logger.exception(f"Error in SentinelLauncher: {e}")
                await asyncio.sleep(self._interval)

    def stop(self):
        """Stop the background worker"""
        self._running = False

        # Stop all running sentinels
        for sentinel in self.sentinels.values():
            sentinel.stop()

    async def watch_watched(self):
        """Check watched AIDs and launch sentinels as needed"""
        for (_, _, oid), observed in self.hby.db.obvs.getItemIter(
            keys=(
                self.cid,
                self.hab.pre,
            )
        ):
            if observed.enabled and oid not in self.sentinels:
                dtnow = helping.nowUTC()
                dte = helping.fromIso8601(observed.datetime)
                if (dtnow - dte) > timedelta(seconds=self.WATCHERRETRY):
                    sentinel = Sentinel(
                        self.hby,
                        self.hab,
                        self.rgy,
                        oid,
                        self.cid,
                        self.db,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )
                    self.sentinels[oid] = sentinel

                    # Start the sentinel task
                    asyncio.create_task(sentinel.run())

                    observed.datetime = helping.toIso8601(dtnow)
                    self.hby.db.obvs.pin(
                        keys=(self.cid, self.hab.pre, oid), val=observed
                    )


class Escrower:
    """Escrowing processing loop"""

    def __init__(self, kvy, rvy, tvy, exc=None):
        """Process escrows for all message processors

        Parameters:
            kvy(Kevery): key event log message processor
            rvy(Revery): reply message processor
            tvy(Tevery): transaction event log message processor
            exc(Exchanger): exchange message processor
        """
        self.kvy = kvy
        self.rvy = rvy
        self.tvy = tvy
        self.exc = exc
        self._running = False
        self._interval = 0.1  # Process escrows every 100ms

    async def run(self):
        """Main loop to process escrows"""
        self._running = True

        while self._running:
            try:
                await self.process_escrows()
                await asyncio.sleep(self._interval)
            except Exception as e:
                logger.exception(f"Error in Escrower: {e}")
                await asyncio.sleep(self._interval)

    def stop(self):
        """Stop the background worker"""
        self._running = False

    async def process_escrows(self):
        """Run through the escrow process for all processors"""
        # These methods are synchronous, so we run them directly
        # If they become blocking, we could run them in an executor
        self.kvy.processEscrows()
        self.rvy.processEscrowReply()
        if self.tvy is not None:
            self.tvy.processEscrows()
        self.exc.processEscrow()


class Sentinel:
    """Watches a specific AID and queries witnesses"""

    def __init__(
        self,
        hby,
        hab,
        rgy,
        oid,
        cid,
        db,
        export_dir: str = "/usr/local/sentinel",
        registrar_url=None,
    ):
        """Create sentinel to watch a specific AID

        Parameters:
            hby: Habery instance
            hab: Habitat of watcher
            rgy: Registry instance for credential management
            oid: Object identifier being watched
            cid: Controller identifier
            db: Database instance
            export_dir: Directory for exporting CESR files
            registrar_url: URL of credential registrar for automatic credential search
        """
        self.hby = hby
        self.hab = hab
        self.oid = oid
        self.cid = cid
        self.db = db
        self.export_dir = export_dir
        self.credential_loader = (
            None
            if not registrar_url
            else CredentialLoader(hby, rgy, export_dir, registrar_url)
        )

        self._task = None
        self._done = False

    @property
    def done(self):
        """Check if the sentinel has completed"""
        return self._done

    async def run(self):
        """Execute the watch operation"""
        try:
            await self.watch()
        except Exception as e:
            logger.exception(f"Error in Sentinel.run: {e}")
        finally:
            self._done = True

    def stop(self):
        """Stop the sentinel"""
        if self._task and not self._task.done():
            self._task.cancel()
        self._done = True

    async def _query_single_witness(self, wit, kever, receiptor, queryTimestamp):
        """Query a single witness for key state (helper for parallel execution)

        Parameters:
            wit: Witness identifier
            kever: Key event verifier
            receiptor: Receiptor instance
            queryTimestamp: ISO8601 timestamp string

        Returns:
            WitnessState or None if query failed
        """
        keys = (self.oid, wit)
        wit_query = WitnessQuery(
            watcher_id=self.hab.pre,
            aid=self.oid,
            wit=wit,
            query_timestamp=queryTimestamp,
            response_received=False,
            state=States.unresponsive,
        )

        try:
            # Check for Key State from this Witness and remove if exists
            saider = self.hby.db.knas.get(keys)
            if saider is not None:
                self.hby.db.knas.rem(keys)
                self.hby.db.ksns.rem((saider.qb64,))

            await receiptor.ksn(pre=self.oid, src=self.hab.pre, wit=wit)

            if (saider := self.hab.db.knas.get(keys)) is None:
                wit_query.error = "No response received within timeout"
                self.db.witq.pin(keys=(self.hab.pre, self.oid, wit), val=wit_query)
                return None

            mystate = kever.state()
            witstate = self.hby.db.ksns.get((saider.qb64,))

            diffstate = self.diff_state(wit, mystate, witstate)
            wit_query.response_received = True
            wit_query.state = diffstate.state  # type: ignore
            wit_query.keystate = witstate
            wit_query.sn = diffstate.sn
            wit_query.dig = diffstate.dig

            self.db.witq.pin(keys=(self.hab.pre, self.oid, wit), val=wit_query)

            return diffstate

        except Exception as e:
            logger.error(f"Error querying witness {wit}: {e}")
            wit_query.error = str(e)
            self.db.witq.pin(keys=(self.hab.pre, self.oid, wit), val=wit_query)
            return None

    async def watch(self):
        """Async method to watch and query witnesses"""
        logger.info(
            f"Launching watcher {self.hab.pre} for {self.oid} on behalf of {self.cid}"
        )
        if self.oid not in self.hby.kevers:
            logger.info(f"Unable to watch unknown aid={self.oid}")
            return

        kever = self.hby.kevers[self.oid]
        if len(kever.wits) == 0:
            logger.info(f"No witnesses for {self.oid} at {kever.sn}, skipping.")
            return

        queryTimestamp = helping.nowIso8601()

        receiptor = querying.Receiptor(hby=self.hby)

        try:
            # Query all witnesses in parallel
            logger.debug(
                f"Querying {len(kever.wits)} witnesses in parallel for {self.oid}"
            )
            results = await asyncio.gather(
                *[
                    self._query_single_witness(wit, kever, receiptor, queryTimestamp)
                    for wit in kever.wits
                ],
                return_exceptions=True,
            )

            # Process results and build states list
            states = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Exception during witness query: {result}")
                    continue
                if result is not None:
                    states.append(result)

            logger.debug(
                f"Received {len(states)} responses from {len(kever.wits)} witnesses"
            )

            # First check for any duplicity, if so get out of here
            dups = [state for state in states if state.state == States.duplicitous]
            ahds = [state for state in states if state.state == States.ahead]

            if len(dups) > 0:
                logger.info(f"{len(dups)} witnesses have a duplicitous event")
                for state in dups:
                    logger.info(
                        f"Duplicitous witness state for {state.wit} at Seq No. {state.sn} with digest: {state.dig}"
                    )
                return

            elif len(ahds) > 0:
                # First check for duplicity among the witnesses that are ahead (possible only if toad is below
                # super majority)
                digs = set([state.dig for state in ahds])
                if len(digs) > 1:  # Duplicity across witness sets
                    logger.info(
                        f"There are multiple duplicitous events on witnesses for {self.oid}"
                    )
                    return

                else:  # all witnesses that are ahead agree on the event
                    logger.info(
                        f"{len(ahds)} witnesses have an event that is ahead of the local KEL:"
                    )

                current_sn = self.hby.kevers[self.oid].sn
                state = random.choice(ahds)
                fn = (
                    self.hby.kevers[self.oid].sn + 1
                    if self.oid in self.hby.kevers
                    else 0
                )

                await receiptor.logs(pre=self.oid, src=self.hab.pre, wit=state.wit, fn=fn, sn=state.sn)  # type: ignore

                # Export KEL after fetching new events
                try:
                    await filing.export_kel(
                        hby=self.hby, aid=self.oid, export_dir=self.export_dir
                    )
                    logger.info(
                        f"Successfully exported KEL for {self.oid} after detecting new events"
                    )
                except Exception as e:
                    logger.error(f"Failed to export KEL for {self.oid}: {e}")

                # Trigger credential search if appropriate
                if self.credential_loader:
                    logger.info(
                        f"Launching credential search for {kever.serder.pre} between {current_sn} and {state.sn}"
                    )
                    asyncio.create_task(
                        self.credential_loader.search_for_credentials(
                            kever.serder.pre, current_sn, state.sn
                        )
                    )

                return

            elif len(states) == 0:
                logger.info(f"Zero witnesses for {self.oid} responded.")
                return
            else:
                state = random.choice(states)
                logger.info(
                    f"Local key state for {self.oid} is consistent at seq no. {state.sn} with the "
                    f"{len(states)} (out of {len(kever.wits)} total) witnesses that responded."
                )
                return
        finally:
            # Always cleanup the receiptor
            await receiptor.stop()

    @staticmethod
    def diff_state(wit, preksn, witksn):
        witstate = WitnessState()
        witstate.wit = wit
        mysn = int(preksn.s, 16)
        mydig = preksn.d
        witstate.sn = int(witksn.f, 16)
        witstate.dig = witksn.d

        # At the same sequence number, check the DIGs
        if mysn == witstate.sn:
            if mydig == witstate.dig:
                witstate.state = States.even
            else:
                witstate.state = States.duplicitous

        # This witness is behind and will need to be caught up.
        elif mysn > witstate.sn:
            witstate.state = States.behind

        # mysn < witstate.sn - We are behind this witness (multisig or restore situation).
        # Must ensure that controller approves this event or a recovery rotation is needed
        else:
            witstate.state = States.ahead

        return witstate


class LocalSocketListener:
    """
    Asyncio-based Unix Domain Socket listener that monitors new obvs entries.

    Listens on a Unix Domain Socket for connections. When a connection is received,
    reads all data from the connection, then checks hby.db.obvs for new entries
    (datetime > last_check) and calls add_watched_identifier for each new entry.
    """

    def __init__(
        self,
        hby: Habery,
        watcher: Watcher,
        db,
        socket_path: str,
        poll_interval: float = 0.5,
    ):
        """
        Initialize the LocalSocketListener.

        Args:
            hby: Habery instance for managing healthKERI accounts
            watcher: Watcher parent class.
            db: Database instance with watched_poll table
            socket_path: Path to Unix Domain Socket (e.g., /tmp/sentinel_name.sock)
            poll_interval: Timer interval for checking connections (default: 0.5 seconds)
        """
        self.hby = hby
        self.watcher = watcher
        self.psr = parsing.Parser(kvy=self.hby.kvy, rvy=self.hby.rvy, local=True)
        self.db = db
        self.socket_path = socket_path
        self.poll_interval = poll_interval
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
        logger.info(f"LocalSocketListener: Starting server on {self.socket_path}")

        try:
            # Remove existing socket file if present
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
                logger.debug(
                    f"LocalSocketListener: Removed existing socket file {self.socket_path}"
                )

            # Create Unix Domain Socket server
            self._server = await asyncio.start_unix_server(
                self._handle_connection, path=self.socket_path
            )

            logger.info(f"LocalSocketListener: Server listening on {self.socket_path}")

            # Run server loop
            while self._running:
                await asyncio.sleep(self.poll_interval)

                # Clean up finished connection tasks
                self._connection_tasks = {
                    task for task in self._connection_tasks if not task.done()
                }

        except asyncio.CancelledError:
            logger.info("LocalSocketListener: Task cancelled")
        except Exception as e:
            logger.exception(f"LocalSocketListener: Error in run loop: {e}")
        finally:
            await self._cleanup()

        logger.info("LocalSocketListener: Stopped")

    async def _cleanup(self):
        """
        Clean up server resources and socket file.
        """
        try:
            logger.info("LocalSocketListener: Cleaning up...")

            # Close server
            if self._server:
                self._server.close()
                await self._server.wait_closed()
                logger.debug("LocalSocketListener: Server closed")

            # Remove socket file
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
                logger.debug(
                    f"LocalSocketListener: Removed socket file {self.socket_path}"
                )

            # Cancel all connection tasks
            if self._connection_tasks:
                logger.debug(
                    f"LocalSocketListener: Cancelling {len(self._connection_tasks)} connection tasks"
                )
                for task in self._connection_tasks:
                    task.cancel()

                # Wait for all tasks to complete
                await asyncio.gather(*self._connection_tasks, return_exceptions=True)

        except Exception as e:
            logger.exception(f"LocalSocketListener: Error during cleanup: {e}")

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
        logger.info(f"LocalSocketListener: New connection from {peer}")

        try:
            # Read all data from connection
            data = bytearray()
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                data.extend(chunk)

            logger.debug(f"LocalSocketListener: Received {len(data)} bytes from {peer}")

            # Check and add new obvs entries
            self.psr.parseOne(data)
            await self._resolve_oobis()
            await self._check_and_add_obvs()

        except Exception as e:
            logger.exception(
                f"LocalSocketListener: Error processing connection from {peer}: {e}"
            )
        finally:
            try:
                writer.close()
                await writer.wait_closed()
                logger.info(f"LocalSocketListener: Connection from {peer} closed")
            except Exception as e:
                logger.exception(f"LocalSocketListener: Error closing connection: {e}")

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
                    "LocalSocketListener: No DB available, skipping obvs check"
                )
                return

            if not self.db.watched_poll:
                logger.warning(
                    "LocalSocketListener: watched_poll database not available"
                )
                return

            if not hasattr(self.hby.db, "obvs"):
                logger.warning("LocalSocketListener: obvs database not available")
                return

            # Get last check timestamp from database
            last_check_dater = self.db.watched_poll.get(keys=("obvs_last",))

            if last_check_dater:
                last_check_dt = datetime.fromisoformat(last_check_dater.dts)
                logger.debug(f"LocalSocketListener: Last check time: {last_check_dt}")
            else:
                # First check - use epoch
                last_check_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
                logger.debug(
                    f"LocalSocketListener: First check, using epoch {last_check_dt}"
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
                            f"LocalSocketListener: Skipping obvs entry without datetime - oid={oid}"
                        )
                        continue

                    observed_dt = datetime.fromisoformat(observed.datetime)

                    if observed_dt > last_check_dt:
                        new_count += 1
                        logger.info(
                            f"LocalSocketListener: New obvs entry - cid={cid}, aid={aid}, oid={oid}, "
                            f"name={getattr(observed, 'name', 'N/A')}, datetime={observed.datetime}"
                        )

                        # Add watched identifier
                        self.watcher.watch(oid)
                        alias = getattr(observed, "name", oid)
                        logger.info(
                            f"LocalSocketListener: Successfully added watched identifier - "
                            f"oid={oid}, alias={alias}"
                        )

                except Exception as e:
                    error_count += 1
                    logger.exception(
                        f"LocalSocketListener: Error processing obvs entry (oid={oid}): {e}"
                    )
                    continue

            # Update last check timestamp to now
            now = datetime.now(timezone.utc)
            now_dater = coring.Dater(dts=now.isoformat())
            self.db.watched_poll.pin(keys=("obvs_last",), val=now_dater)
            logger.debug(f"LocalSocketListener: Updated last check time to {now}")

            logger.info(
                f"LocalSocketListener: Processed {new_count} new obvs entries - "
                f"success={success_count}, errors={error_count}"
            )

        except Exception as e:
            logger.exception(f"LocalSocketListener: Error in _check_and_add_obvs: {e}")

    async def _resolve_oobis(self):
        for (oobi,), oobi_record in self.hby.db.oobis.getItemIter():
            async with httpx.AsyncClient() as client:
                response = await client.get(oobi)
                if response.status_code == 200:
                    self.psr.parse(response.content)
                    self._process_escrows()
                    self.hby.db.oobis.rem(keys=(oobi,))

    def _process_escrows(self):
        self.hby.kvy.processEscrows()
        self.hby.rvy.processEscrowReply()

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
