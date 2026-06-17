# -*- encoding: utf-8 -*-
"""
sentinel.core.oobiing module

"""

import asyncio
import datetime
import logging
from collections import namedtuple
from urllib import parse
from urllib.parse import urlparse

import httpx

from keri.core import coring
from keri import help
from keri import kering
from keri.app import connecting
from keri.core import routing, eventing, parsing, scheming, serdering
from keri.db import basing
from keri.end import ending
from keri.end.ending import OOBI_RE, DOOBI_RE
from keri.help import helping
from keri.kering import Ilks, ValidationError, UnverifiedReplyError, ConfigurationError

logger = help.ogler.getLogger()

Resultage = namedtuple("Resultage", "resolved failed")  # stream cold start status
Result = Resultage(resolved="resolved", failed="failed")


class Oobiery:
    """Resolver for OOBIs"""

    RetryDelay = 30
    MaxRetries = 3

    def __init__(self, hby, rvy=None):
        """DoDoer to handle the request and parsing of OOBIs

        Parameters:
            hby (Habery): database environment
            rvy (routing.Revery): reply processing environment

        """

        self.hby = hby
        self.rvy = rvy
        if self.rvy is not None:
            self.register_reply_routes(self.rvy.rtr)

        self.org = connecting.Organizer(hby=self.hby)
        self.client = httpx.AsyncClient(timeout=30.0)

        # Set up a local parser for returned events from OOBI queries.
        rtr = routing.Router()
        rvy = routing.Revery(db=self.hby.db, rtr=rtr)
        kvy = eventing.Kevery(db=self.hby.db, lax=True, local=False, rvy=rvy)
        kvy.registerReplyRoutes(router=rtr)
        self.parser = parsing.Parser(framed=True, kvy=kvy, rvy=rvy)

        self._running = False
        self._oobi_task = None

    def start(self):
        """Start background worker tasks"""
        self._running = True
        self._oobi_task = asyncio.create_task(self.process_flows())

        return [self._oobi_task]

    async def stop(self):
        """Stop background workers and cleanup resources"""
        self._running = False
        if self._oobi_task and not self._oobi_task.done():
            self._oobi_task.cancel()

        await self.client.aclose()

    async def process_flows(self):
        """
        Asynchronous function that continuously processes OOBI (Out-of-Band Introduction) flows.

        This function runs indefinitely in a loop, invoking the `processFlows` method periodically
        with a fixed time interval. It manages the execution flow of OOBI processes by handling
        their processing in recurring intervals.

        Raises:
            RuntimeError: If the asyncio event loop is closed.

        """

        while self._running:
            try:
                await asyncio.sleep(3.0)
                await self.process_oobis()
                self.process_retries()
                self.process_moobis()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Error in witDo: {e}")

    async def process_oobis(self):
        """Process OOBI records loaded for discovery

        There should be only one OOBIERY that minds the OOBI table, this should read from the table like an escrow

        """
        for (url,), obr in self.hby.db.oobis.getItemIter():
            try:
                # Don't process OOBIs we've already resolved or are in escrow being retried
                if (
                    (fnd := self.hby.db.roobi.get(keys=(url,))) is not None
                    and fnd.state == Result.resolved
                ) and self.hby.db.eoobi.get(keys=(url,)) is not None:
                    logging.info(f"OOBI {url} already resolved, skipping")
                    self.hby.db.oobis.rem(keys=(url,))
                    continue

                purl = parse.urlparse(url)

                if purl.path == "/oobi":  # Self and Blinded Introductions
                    params = parse.parse_qs(purl.query)

                    # If name is hinted in query string, use it as alias if not provided in OOBIRecord
                    if "name" in params and obr.oobialias is None:
                        obr.oobialias = params["name"][0]

                    response = await self.request(
                        url,
                    )
                    self.process_response(response, url, obr)

                elif (
                    match := OOBI_RE.match(purl.path)
                ) is not None:  # Full CID and optional EID
                    obr.cid = match.group("cid")
                    obr.eid = match.group("eid")
                    obr.role = match.group("role")
                    params = parse.parse_qs(purl.query)

                    # If name is hinted in query string, use it as alias if not provided in OOBIRecord
                    if "name" in params and obr.oobialias is None:
                        obr.oobialias = params["name"][0]

                    response = await self.request(url)
                    self.process_response(response, url, obr)

                elif (
                    match := DOOBI_RE.match(purl.path)
                ) is not None:  # Full CID and optional EID
                    obr.said = match.group("said")
                    response = await self.request(url)
                    self.process_response(response, url, obr)

                elif (
                    match := ending.WOOBI_RE.match(purl.path)
                ) is not None:  # Well Known
                    obr.cid = match.group("cid")
                    params = parse.parse_qs(purl.query)

                    # If name is hinted in query string, use it as alias if not provided in OOBIRecord
                    if "name" in params and obr.oobialias is None:
                        obr.oobialias = params["name"][0]

                    response = await self.request(url)
                    self.process_response(response, url, obr)

            except ValueError as ex:
                print(f"error requesting invalid OOBI URL {ex}", url)

    def process_response(self, response, url, obr):
        """Process Client responses by parsing the messages and removing the client/doer"""
        if response.status_code == 404:
            logger.info(f"{url} not found")
            self.hby.db.eoobi.pin(keys=(url,), val=obr)
            return

        elif not response.status_code == 200:
            logger.info(
                "invalid status for oobi response: {}".format(response.status_code)
            )
            self.hby.db.oobis.rem(keys=(url,))
            obr.state = Result.failed
            self.hby.db.roobi.put(keys=(url,), val=obr)

        elif response.headers["Content-Type"] in (
            "application/json+cesr",
            "application/cesr",
        ):  # CESR Stream response to OOBI
            self.parser.parse(ims=bytearray(response.content))
            if ending.OOBI_AID_HEADER in response.headers:
                obr.cid = response.headers[ending.OOBI_AID_HEADER]

            if obr.oobialias is not None and obr.cid:
                self.org.update(pre=obr.cid, data=dict(alias=obr.oobialias, oobi=url))

            self.hby.db.oobis.rem(keys=(url,))
            obr.state = Result.resolved
            self.hby.db.roobi.put(keys=(url,), val=obr)
            logger.info(f"OOBI {url} resolved successfully")

        elif (
            response.headers["Content-Type"] == "application/schema+json"
        ):  # Schema response to data OOBI
            try:
                schemer = scheming.Schemer(raw=bytearray(response.content))
                if schemer.said == obr.said:
                    self.hby.db.schema.pin(keys=(schemer.said,), val=schemer)
                    result = Result.resolved
                else:
                    result = Result.failed

            except (kering.ValidationError, ValueError):
                result = Result.failed

            obr.state = result
            self.hby.db.oobis.rem(keys=(url,))
            self.hby.db.roobi.put(keys=(url,), val=obr)

        elif response.headers["Content-Type"].startswith(
            "application/json"
        ):  # Unsigned rpy OOBI or Schema

            try:
                schemer = scheming.Schemer(raw=bytearray(response.content))
                if schemer.said == obr.said:
                    self.hby.db.schema.pin(keys=(schemer.said,), val=schemer)
                    result = Result.resolved
                else:
                    result = Result.failed

                obr.state = result
                self.hby.db.oobis.rem(keys=(url,))
                self.hby.db.roobi.put(keys=(url,), val=obr)
                return

            except (kering.ValidationError, ValueError):
                pass

            try:
                serder = serdering.SerderKERI(raw=bytearray(response.content))
            except ValueError:
                obr.state = Result.failed
                self.hby.db.oobis.rem(keys=(url,))
                self.hby.db.roobi.put(keys=(url,), val=obr)
                return

            if not serder.ked["t"] == coring.Ilks.rpy:
                obr.state = Result.failed
                self.hby.db.oobis.rem(keys=(url,))
                self.hby.db.roobi.put(keys=(url,), val=obr)

            elif serder.ked["r"] in ("/oobi/witness", "/oobi/controller"):
                self.process_multi_oobi_rpy(url, serder, obr)

            else:
                obr.state = Result.failed
                self.hby.db.oobis.rem(keys=(url,))
                self.hby.db.roobi.put(keys=(url,), val=obr)

        else:
            self.hby.db.oobis.rem(keys=(url,))
            obr.state = Result.failed
            self.hby.db.roobi.put(keys=(url,), val=obr)
            logger.error(
                "invalid content type for oobi response: {}".format(
                    response.headers["Content-Type"]
                )
            )

    def process_moobis(self):
        """Process Client responses by parsing the messages and removing the client/doer"""
        for (url,), obr in self.hby.db.moobi.getItemIter():
            result = Result.resolved
            complete = True
            for oobi in obr.urls:
                robr = self.hby.db.roobi.get(keys=(oobi,))
                if not robr:
                    complete = False
                    break
                if robr.state == Result.failed:
                    result = Result.failed

            if complete:
                obr.state = result
                self.hby.db.oobis.rem(keys=(url,))
                self.hby.db.roobi.put(keys=(url,), val=obr)

    def process_retries(self):
        """Process Client responses by parsing the messages and removing the client/doer"""
        for (url,), obr in self.hby.db.eoobi.getItemIter():
            last = helping.fromIso8601(obr.date)
            now = helping.nowUTC()
            if (now - last) > datetime.timedelta(seconds=self.RetryDelay):
                obr.date = helping.toIso8601(now)
                self.hby.db.eoobi.rem(keys=(url,))
                if obr.retries < self.MaxRetries:
                    obr.retries += 1
                    self.hby.db.oobis.pin(keys=(url,), val=obr)

    async def request(self, url):

        try:
            response = await self.client.get(url)
            return response
        except httpx.HTTPError as e:
            logger.error(f"HTTP error posting to {url}: {e}")
            raise

    def process_multi_oobi_rpy(self, url, serder, mobr):
        data = serder.ked["a"]
        cid = data["aid"]

        if cid != mobr.cid:
            return Result.failed

        urls = data["urls"]
        mobr.urls = urls

        for murl in urls:
            obr = basing.OobiRecord(date=helping.nowIso8601())
            obr.oobialias = mobr.oobialias
            obr.cid = mobr.cid
            self.hby.db.oobis.put(keys=(murl,), val=obr)

        self.hby.db.oobis.rem(keys=(url,))
        self.hby.db.moobi.put(keys=(url,), val=mobr)
        return Result.resolved

    def register_reply_routes(self, router):
        """Register the routes for processing messages embedded in `rpy` event messages

        The Oobiery handles rpy messages with the /introduce route by processing the contained oobi

        Parameters:
            router(Router): reply message router

        """
        router.addRoute("/introduce", self)

    def process_reply(self, *, serder, saider, route, cigars=None, tsgs=None):
        """
        Process one reply message for route = /introduce
        with either attached nontrans receipt couples in cigars or attached trans
        indexed sig groups in tsgs.
        Assumes already validated saider, dater, and route from serder.ked

        Parameters:
            serder (SerderKERI): instance of reply msg (SAD)
            saider (Saider): instance  from said in serder (SAD)
            route (str): reply route
            cigars (list): of Cigar instances that contain nontrans signing couple
                          signature in .raw and public key in .verfer
            tsgs (list): tuples (quadruples) of form
                (prefixer, seqner, diger, [sigers]) where:
                prefixer is pre of trans endorser
                seqner is sequence number of trans endorser's est evt for keys for sigs
                diger is digest of trans endorser's est evt for keys for sigs
                [sigers] is list of indexed sigs from trans endorser's keys from est evt

        OobiRecord:
            date: str = date time of reply message of the introduction

        Reply Message:
        {
          "v" : "KERI10JSON00011c_",
          "t" : "rpy",
          "d": "EZ-i0d8JZAoTNZH3ULaU6JR2nmwyvYAfSVPzhzS6b5CM",
          "dt": "2020-08-22T17:50:12.988921+00:00",
          "r" : "/introduce",
          "a" :
          {
             "cid": "ENcOes8_t2C7tck4X4j61fSm0sWkLbZrEZffq7mSn8On",
             "oobi":  "http://localhost:5632/oobi/ENcOes8_t2C7tck4X4j61fSm0sWkLbZrEZffq7mSn8On/witness",
          }
        }

        """
        if route != "/introduce":
            raise ValidationError(
                f"Usupported route={route} in {Ilks.rpy} " f"msg={serder.ked}."
            )

        data = serder.ked["a"]
        dt = serder.ked["dt"]

        for k in ("cid", "oobi"):
            if k not in data:
                raise ValidationError(
                    f"Missing element={k} from attributes in"
                    f" {Ilks.rpy} msg={serder.ked}."
                )

        cider = coring.Prefixer(qb64=data["cid"])  # raises error if unsupported code
        cid = cider.qb64  # controller authorizing eid at role
        aid = cid  # authorizing attribution id

        eider = coring.Prefixer(qb64=data["eid"])  # raises error if unsupported code
        eid = eider.qb64  # endpoint eid at role

        oobi = data["oobi"]
        url = urlparse(oobi)
        if url.scheme not in ("http", "https"):
            raise ValidationError(
                f"Invalid url scheme for introduced OOBI scheme={url.scheme}"
            )

        if self.rvy is None:
            raise ConfigurationError(
                "this oobiery is not configured to handle rpy introductions"
            )

        # Process BADA RUN but with no previous reply message, always process introductions
        accepted = self.rvy.acceptReply(
            serder=serder,
            saider=saider,
            route=route,
            aid=aid,
            osaider=None,
            cigars=cigars,
            tsgs=tsgs,
        )
        if not accepted:
            raise UnverifiedReplyError(f"Unverified introduction reply. {serder.ked}")

        obr = basing.OobiRecord(cid=eid, date=dt)
        self.hby.db.oobis.put(keys=(oobi,), val=obr)
