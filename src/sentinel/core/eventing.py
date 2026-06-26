# -*- coding: utf-8 -*-
"""
sentinel.core.eventing module

"""

import json
from email.message import Message
from urllib.parse import urljoin

import httpx
from keri import kering
from keri.app import habbing
from keri.core import eventing, parsing, serdering, coring
from keri.db import dbing
from requests_toolbelt import MultipartDecoder


async def sync_server_key_state(name, alias, base, bran, essr):
    hby = habbing.Habery(name=name, base=base, bran=bran)
    hab = hby.habByName(alias)
    if not hab:
        raise ValueError(f"Server alias '{alias}' not found in Habery '{name}'")

    kever = hab.kever
    ser = kever.serder
    dgkey = dbing.dgKey(ser.preb, ser.saidb)

    seal = hab.db.getAes(dgkey)
    if not seal and hab.kever.delpre:
        delegator_aid = hab.kever.delpre
        response = await essr.request(
            f"/identifiers/{delegator_aid}?kel=true", method="GET"
        )

        decoder = MultipartDecoder.from_response(response)
        # Parse multipart response
        data = ims = None
        for part in decoder.parts:
            msg = Message()
            msg["content-type"] = part.headers[b"content-disposition"].decode("utf-8")
            params = dict(msg.get_params() or {})

            if params["name"] == "doc":
                # We are expecting a CESR stream of an inception event
                data = json.loads(part.content.decode("utf-8"))

            elif params["name"] == "cesr":
                # We are expecting a CESR stream of a KEL event
                ims = part.content

        delegator_current_sn = int(data.get("key_state", {}).get("s", "0"), 16)

        kvy = eventing.Kevery(db=hab.db, local=True, lax=True)
        parsing.Parser().parse(ims=ims, kvy=kvy)

        if delegator_current_sn != hby.kevers[delegator_aid].sn:
            raise ValueError(
                f"Delegator {delegator_aid} has a different current sequence number than the authorizer"
            )

        for dig in hby.db.getKelIter(hab.pre, sn=0):
            dgkey = dbing.dgKey(hab.pre, dig)
            eraw = hby.db.getEvt(dgkey)
            if eraw is None:
                continue
            event_serder = serdering.SerderKERI(raw=bytes(eraw))  # escrowed event
            seal = dict(i=event_serder.pre, s=event_serder.snh, d=event_serder.said)

            if dserder := hby.db.fetchLastSealingEventByEventSeal(
                delegator_aid, seal=seal
            ):
                seqner = coring.Seqner(sn=dserder.sn)
                couple = seqner.qb64b + dserder.saidb
                dgkey = dbing.dgKey(kever.prefixer.qb64b, kever.serder.saidb)
                hby.db.setAes(dgkey, couple)  # authorizer event seal (delegator/issuer)

    wigs = hab.db.getWigs(dgkey)
    if not wigs:
        for dig in hby.db.getKelIter(hab.pre, sn=0):
            dgkey = dbing.dgKey(hab.pre, dig)
            eraw = hby.db.getEvt(dgkey)
            if eraw is None:
                continue
            event_serder = serdering.SerderKERI(raw=bytes(eraw))  # escrowed event

            for wit in hab.kever.wits:
                urls = hab.fetchUrls(
                    eid=wit, scheme=kering.Schemes.http
                ) or hab.fetchUrls(eid=wit, scheme=kering.Schemes.https)
                if not urls:
                    raise kering.MissingEntryError(
                        f"unable to query witness {wit}, no http endpoint"
                    )

                base = (
                    urls[kering.Schemes.http]
                    if kering.Schemes.http in urls
                    else urls[kering.Schemes.https]
                )
                receipt_url = urljoin(
                    base, f"/receipts?pre={hab.pre}&sn={event_serder.sn}"
                )

                async with httpx.AsyncClient() as client:
                    headers = {"CESR-DESTINATION": wit}
                    response = await client.get(receipt_url, headers=headers)
                    if response.status_code == 200:
                        rct = bytearray(response.content)
                        hab.psr.parseOne(rct)
