# -*- encoding: utf-8 -*-
"""
sentinel.core.querying module

Functions and services for executing queries against Witnesses

"""

import asyncio
import logging
import random
from typing import Optional
from urllib.parse import urljoin

import httpx
from keri import kering, core
from keri.app.httping import (
    CESR_DESTINATION_HEADER,
    CESR_CONTENT_TYPE,
    CESR_ATTACHMENT_HEADER,
)
from keri.core import serdering, coring, eventing

logger = logging.getLogger(__name__)


class Receiptor:
    """Async witness receipt and query handler"""

    def __init__(self, hby, msgs=None, gets=None, cues=None):
        """Initialize Receiptor with asyncio queues and httpx client

        Parameters:
            hby: Habery instance for key state management
            msgs: Optional asyncio.Queue for receipt messages
            gets: Optional asyncio.Queue for query messages
            cues: Optional asyncio.Queue for completion notifications
        """
        self.msgs = msgs if msgs is not None else asyncio.Queue()
        self.gets = gets if gets is not None else asyncio.Queue()
        self.cues = cues if cues is not None else asyncio.Queue()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.hby = hby
        self._running = False
        self._wit_task = None
        self._git_task = None

    async def start(self):
        """Start background worker tasks"""
        self._running = True
        self._wit_task = asyncio.create_task(self.witDo())
        self._git_task = asyncio.create_task(self.gitDo())

    async def stop(self):
        """Stop background workers and cleanup resources"""
        self._running = False
        if self._wit_task:
            self._wit_task.cancel()
            try:
                await self._wit_task
            except asyncio.CancelledError:
                pass
        if self._git_task:
            self._git_task.cancel()
            try:
                await self._git_task
            except asyncio.CancelledError:
                pass
        await self.client.aclose()

    def _build_witness_url(self, hab, wit: str, path: str) -> str:
        """Build URL for witness endpoint

        Parameters:
            hab: Habitat instance
            wit: Witness identifier
            path: API endpoint path

        Returns:
            str: Complete URL for witness endpoint

        Raises:
            kering.MissingEntryError: If witness has no HTTP endpoint
        """
        urls = hab.fetchUrls(eid=wit, scheme=kering.Schemes.http) or hab.fetchUrls(
            eid=wit, scheme=kering.Schemes.https
        )
        if not urls:
            raise kering.MissingEntryError(
                f"unable to query witness {wit}, no http endpoint"
            )

        base = (
            urls[kering.Schemes.http]
            if kering.Schemes.http in urls
            else urls[kering.Schemes.https]
        )
        return urljoin(base, path)

    async def _post_cesr(
        self, url: str, dest: str, msg: bytearray, headers: Optional[dict] = None
    ) -> httpx.Response:
        """Post CESR-encoded data to witness endpoint

        Parameters:
            url: Target URL
            dest: Destination header value
            msg: CESR-encoded payload
            headers: Optional HTTP headers

        Returns:
            httpx.Response: HTTP response
        """
        headers = headers or {}
        try:
            serder = serdering.SerderKERI(raw=msg)
        except kering.ShortageError:  # need more bytes
            raise kering.ExtractionError(
                "unable to extract a valid message to send as HTTP"
            )
        else:  # extracted successfully
            del msg[: serder.size]  # strip off event from front of ims

        attachments = bytes(msg)
        body = serder.raw

        headers["Content-Type"] = CESR_CONTENT_TYPE
        headers["Content-Length"] = f"{len(body)}"
        headers["connection"] = "close"
        headers[CESR_ATTACHMENT_HEADER] = attachments
        headers[CESR_DESTINATION_HEADER] = dest

        try:
            response = await self.client.post(url, content=body, headers=headers)
            return response
        except httpx.HTTPError as e:
            logger.error(f"HTTP error posting to {url}: {e}")
            raise

    async def _get(self, url: str, headers: Optional[dict] = None) -> httpx.Response:
        """Execute GET request

        Parameters:
            url: Target URL
            headers: Optional HTTP headers

        Returns:
            httpx.Response: HTTP response
        """
        headers = headers or {}
        try:
            response = await self.client.get(url, headers=headers)
            return response
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting from {url}: {e}")
            raise

    async def _query_witness_for_receipt(self, hab, wit, msg, auths):
        """Query a single witness for receipt (helper for parallel execution)

        Parameters:
            hab: Habitat instance
            wit: Witness identifier
            msg: Message bytes to submit
            auths: Authorization headers dict

        Returns:
            tuple: (wit, receipt_bytes) if successful, (wit, None) if failed
        """
        try:
            url = self._build_witness_url(hab, wit, "/receipts")
            headers = {CESR_DESTINATION_HEADER: wit, "Content-Type": CESR_CONTENT_TYPE}
            if wit in auths:
                headers["Authorization"] = auths[wit]

            response = await self._post_cesr(url, wit, bytearray(msg), headers)
            if response.status_code == 200:
                rct = bytearray(response.content)
                hab.psr.parseOne(bytearray(rct))
                rserder = serdering.SerderKERI(raw=rct)
                del rct[: rserder.size]

                # pull off the count code
                core.Counter(qb64b=rct, strip=True, gvrsn=kering.Vrsn_1_0)
                return wit, rct
            else:
                logger.warning(
                    f"invalid response {response.status_code} from witness {wit}: {response.text}"
                )
                return wit, None
        except (kering.MissingEntryError, httpx.HTTPError) as e:
            logger.error(f"unable to get receipt from witness {wit}: {e}")
            return wit, None

    async def _propagate_receipt_to_witness(self, hab, wit, msg_bytes):
        """Propagate receipt to a single witness (helper for parallel execution)

        Parameters:
            hab: Habitat instance
            wit: Witness identifier
            msg_bytes: Message bytes to propagate

        Returns:
            bool: True if successful, False if failed
        """
        try:
            url = self._build_witness_url(hab, wit, "/receipts")
            headers = {CESR_DESTINATION_HEADER: wit}
            await self._post_cesr(url, wit, bytearray(msg_bytes), headers)
            return True
        except (kering.MissingEntryError, httpx.HTTPError) as e:
            logger.error(f"unable to propagate receipts to witness {wit}: {e}")
            return False

    async def receipt(self, pre, sn=None, auths: Optional[dict] = None):
        """Submit designated event to witnesses for receipts

        Submits the event to witnesses using the synchronous witness API,
        then propagates the receipts to each of the other witnesses.
        Uses asyncio.gather() for parallel witness queries.

        Parameters:
            pre (str): qualified base64 identifier to gather receipts for
            sn (Optional[int]): sequence number of event to gather receipts for, latest is used if not provided
            auths (Optional[dict]): map of witness AIDs to (time,auth) tuples for providing TOTP auth for witnessing

        Returns:
            list: identifiers of witnesses that returned receipts.
        """
        auths = auths if auths is not None else dict()
        if pre not in self.hby.prefixes:
            raise kering.MissingEntryError(f"{pre} not a valid AID")

        hab = self.hby.habs[pre]
        sn = sn if sn is not None else hab.kever.sner.num
        wits = hab.kever.wits

        if len(wits) == 0:
            return []

        msg = hab.makeOwnEvent(sn=sn)
        ser = serdering.SerderKERI(raw=bytes(msg))

        # If we are a rotation event, may need to catch new witnesses up to current key state
        if ser.ked["t"] in (coring.Ilks.rot,):
            adds = ser.ked["ba"]
            # Catchup new witnesses in parallel
            if adds:
                await asyncio.gather(
                    *[self.catchup(ser.pre, wit) for wit in adds],
                    return_exceptions=True,
                )

        # Collect receipts from all witnesses in parallel
        logger.debug(f"Querying {len(wits)} witnesses in parallel for receipts")
        results = await asyncio.gather(
            *[self._query_witness_for_receipt(hab, wit, bytes(msg), auths) for wit in wits],  # type: ignore
            return_exceptions=True,
        )

        # Process results and build receipts dict
        rcts = dict()
        for result in results:
            if isinstance(result, Exception):
                import traceback

                traceback.print_exception(type(result), result, result.__traceback__)
                logger.error(f"Exception during witness query: {result}")
                continue
            wit, rct = result
            if rct is not None:
                rcts[wit] = rct

        logger.debug(f"Received {len(rcts)} receipts from {len(wits)} witnesses")

        # Propagate receipts to other witnesses in parallel
        if rcts:
            propagation_tasks = []
            for wit in rcts:
                ewits = [w for w in rcts if w != wit]
                wigs = [sig for w, sig in rcts.items() if w != wit]

                msg_bytes = bytearray()
                if ser.ked["t"] in (
                    coring.Ilks.icp,
                    coring.Ilks.dip,
                ):  # introduce new witnesses
                    from keri.app.agenting import schemes

                    msg_bytes.extend(schemes(self.hby.db, eids=ewits))
                elif ser.ked["t"] in (coring.Ilks.rot, coring.Ilks.drt) and (
                    "ba" in ser.ked and wit in ser.ked["ba"]
                ):  # Newly added witness, introduce to all
                    from keri.app.agenting import schemes

                    msg_bytes.extend(schemes(self.hby.db, eids=ewits))

                rserder = eventing.receipt(pre=hab.pre, sn=sn, said=ser.said)
                msg_bytes.extend(rserder.raw)
                msg_bytes.extend(
                    core.Counter(
                        core.Codens.NonTransReceiptCouples,
                        count=len(wigs),
                        gvrsn=kering.Vrsn_1_0,
                    ).qb64b
                )
                for wig in wigs:
                    msg_bytes.extend(wig)

                propagation_tasks.append(
                    self._propagate_receipt_to_witness(hab, wit, msg_bytes)
                )

            # Execute all propagations in parallel
            logger.debug(
                f"Propagating receipts to {len(propagation_tasks)} witnesses in parallel"
            )
            await asyncio.gather(*propagation_tasks, return_exceptions=True)

        return list(rcts.keys())

    async def get(self, pre, sn=None):
        """Query random witness for receipts

        Parameters:
            pre (str): qualified base64 identifier to gather receipts for
            sn (Optional[int]): sequence number of event to gather receipts for, latest is used if not provided

        Returns:
            bool: True if witness returned receipts
        """
        if pre not in self.hby.prefixes:
            raise kering.MissingEntryError(f"{pre} not a valid AID")

        hab = self.hby.habs[pre]
        sn = sn if sn is not None else hab.kever.sner.num
        wits = hab.kever.wits

        if len(wits) == 0:
            return False

        wit = random.choice(hab.kever.wits)
        try:
            url = self._build_witness_url(hab, wit, f"/receipts?pre={pre}&sn={sn}")
            headers = {CESR_DESTINATION_HEADER: wit}

            response = await self._get(url, headers)
            if response.status_code == 200:
                rct = bytearray(response.content)
                hab.psr.parseOne(bytearray(rct))
                return True
            return False
        except (kering.MissingEntryError, httpx.HTTPError) as e:
            logger.error(f"unable to query witness {wit}: {e}")
            return False

    async def ksn(self, pre, wit, src):
        """Query witness for key state notice

        Parameters:
            pre (str): qualified base64 identifier to gather receipts for
            wit (str): qualified base64 identifier of the witness to query
            src (str): the source qualified base64 identifier of the source of the query

        Returns:
            bool: True if the witness responded with a key state notice
        """
        if src not in self.hby.prefixes:
            raise kering.MissingEntryError(f"{pre} not a valid AID")

        hab = self.hby.habs[src]
        kever = hab.kevers[pre]
        wits = kever.wits

        if wit not in wits:
            return False

        try:
            url = self._build_witness_url(hab, wit, f"/ksn?pre={pre}&src={src}")
            headers = {CESR_DESTINATION_HEADER: wit}

            response = await self._get(url, headers)
            if response.status_code == 200:
                rct = bytearray(response.content)
                hab.psr.parseOne(bytearray(rct))
                return True
            return False
        except (kering.MissingEntryError, httpx.HTTPError) as e:
            logger.error(f"unable to query witness {wit}: {e}")
            return False

    async def logs(self, pre, wit, src, sn=None, fn=None, anchor=None):
        """Query witness for event logs

        Parameters:
            pre (str): qualified base64 identifier to gather receipts for
            wit (str): qualified base64 identifier of the witness to query
            src (str): the source qualified base64 identifier of the source of the query
            sn (Optional[int]): sequence number to query
            fn (Optional[int]): first seen number to query
            anchor (Optional[str]): anchor to query

        Returns:
            bool: True if the witness responded with logs
        """
        if src not in self.hby.prefixes:
            raise kering.MissingEntryError(f"{pre} not a valid AID")

        hab = self.hby.habs[src]
        kever = hab.kevers[pre]
        wits = kever.wits

        if wit not in wits:
            return False

        try:
            params = [f"pre={pre}"]
            if sn is not None:
                params.append(f"s={sn:X}")
            if fn is not None:
                params.append(f"fn={fn:X}")
            if anchor:
                params.append(f"a={anchor}")

            params_str = "&".join(params)
            url = self._build_witness_url(hab, wit, f"/log?{params_str}")
            headers = {CESR_DESTINATION_HEADER: wit}

            response = await self._get(url, headers)
            if response.status_code == 200:
                ims = bytearray(response.content)
                hab.psr.parse(bytearray(ims))
                return True
            else:
                logger.info(
                    f"Failed to retrieve log from {wit}: {response.status_code}"
                )
                return False
        except (kering.MissingEntryError, httpx.HTTPError) as e:
            logger.error(f"unable to query logs from witness {wit}: {e}")
            return False

    async def catchup(self, pre, wit, batch_size=10):
        """Catch witness up to current state of the KEL

        When adding a new Witness, use this method to send the entire KEL
        to the witness to catch it up to the current state.
        Events are sent in batches for better performance.

        Parameters:
            pre (str): qualified base64 AID of the KEL to send
            wit (str): qualified base64 AID of the witness to send the KEL to
            batch_size (int): number of events to send in parallel per batch (default: 10)
        """
        if pre not in self.hby.prefixes:
            raise kering.MissingEntryError(f"{pre} not a valid AID")

        hab = self.hby.habs[pre]

        try:
            url = self._build_witness_url(hab, wit, "/receipts")
            headers = {CESR_DESTINATION_HEADER: wit}

            # Collect all KEL events
            events = list(hab.db.clonePreIter(pre=pre))

            if not events:
                logger.debug(f"No events to send for catchup to witness {wit}")
                return

            logger.debug(
                f"Catching up witness {wit} with {len(events)} events in batches of {batch_size}"
            )

            # Send events in batches for better performance while maintaining order
            for i in range(0, len(events), batch_size):
                batch = events[i : i + batch_size]

                # Send this batch in parallel
                tasks = [
                    self._post_cesr(url, wit, bytearray(fmsg), headers)
                    for fmsg in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check for errors in this batch
                for idx, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"Error sending event {i + idx} to witness {wit}: {result}"
                        )

            logger.debug(f"Completed catchup for witness {wit}")

        except (kering.MissingEntryError, httpx.HTTPError) as e:
            logger.error(f"unable to catchup witness {wit}: {e}")

    async def witDo(self):
        """Background task for processing msgs queue

        Processes receipt requests from the msgs queue and sends them to witnesses.
        """
        while self._running:
            try:
                msg = await asyncio.wait_for(self.msgs.get(), timeout=0.5)
                pre = msg["pre"]
                sn = msg.get("sn")
                auths = msg.get("auths")

                await self.receipt(pre, sn, auths)
                await self.cues.put(msg)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Error in witDo: {e}")

    async def gitDo(self):
        """Background task for processing gets queue

        Processes query requests from the gets queue.
        """
        while self._running:
            try:
                msg = await asyncio.wait_for(self.gets.get(), timeout=0.5)
                pre = msg["pre"]
                sn = msg.get("sn")

                await self.get(pre, sn)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Error in gitDo: {e}")
