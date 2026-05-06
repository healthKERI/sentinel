# -*- encoding: utf-8 -*-
"""
KERI
mdc2.app.cli.commands module

Initialize the MDC2 server using the provided auth_key
"""
import argparse
import json

import requests
from hio import help
from keri import core, kering
from keri.app import habbing, connecting
from keri.app.keeping import Algos
from keri.help import helping
from keri.kering import ConfigurationError
from kept.hk.configing import HealthKERIConfig

logger = help.ogler.getLogger()

parser = argparse.ArgumentParser(description="Initialize a new healthKERI machine.")
parser.set_defaults(handler=lambda args: up(args), transferable=True)
parser.add_argument(
    "--name", "-n", help="Name of the database environment", required=True
)
parser.add_argument(
    "--base",
    "-b",
    help="additional optional prefix to file location of KERI keystore",
    required=False,
    default="",
)
parser.add_argument(
    "--alias",
    "-a",
    help="human readable alias for the new identifier prefix",
    required=True,
)
parser.add_argument(
    "--passcode",
    "-p",
    help="21 character encryption passcode for keystore (is not saved)",
    dest="bran",
    default=None,
)  # passcode => bran
parser.add_argument(
    "--salt",
    "-s",
    help="qualified base64 salt for creating key pairs",
    required=False,
    default=None,
)
parser.add_argument(
    "-H",
    "--host",
    dest="host",
    action="store",
    default="127.0.0.1",
    help="Local host IP address the server listens on. Default is 127.0.0.1.",
)
parser.add_argument(
    "--port",
    dest="port",
    action="store",
    default=3000,
    help="Local port number the server listens on. Default is 3000.",
)
parser.add_argument(
    "--auth-key",
    required=True,
    help="The auth-key used to initialize this server with your healthKERI netmap",
)
parser.add_argument(
    "--delegator",
    required=True,
    help="The AID of the delegator for this server.",
)
parser.add_argument(
    "--number-of-witnesses",
    "-w",
    required=False,
    default=3,
    help="The number of witnesses to add for the server. Default is 3.",
)
parser.add_argument(
    "--log-level",
    default="INFO",
    help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)


def up(args):
    config = HealthKERIConfig.get_instance()

    server_name = args.name
    server_alias = args.alias

    sentinel_name = f"{server_name}-sentinel"
    sentinel_alias = f"{server_alias}-sentinel"
    watcher_alias = f"{server_alias}-watcher"

    kwa = dict()
    kwa["salt"] = args.salt
    kwa["bran"] = args.bran
    if args.salt is None:
        kwa["algo"] = Algos.randy
        kwa["salt"] = None
    else:
        kwa["salt"] = core.Salter(raw=args.salt).qb64

    # Create environment and identifier for the ACDC Auth Server
    server_hby = habbing.Habery(name=server_name, base=args.base, temp=False, **kwa)
    if not (server_hab := server_hby.habByName(server_alias)):
        server_hab = server_hby.makeHab(
            name=server_alias,
            transferable=True,
            icount=1,
            isith="1",
            ncount=1,
            nsith="1",
            toad=0,
            delpre=args.delegator,
        )
        dt = helping.nowIso8601()

        msgs = bytearray()
        msgs.extend(server_hab.makeEndRole(eid=server_hab.pre, role=kering.Roles.controller, stamp=dt))
        msgs.extend(
            server_hab.makeLocScheme(
                url=f"{kering.Schemes.http}://{args.host}:{args.port}/",
                scheme=kering.Schemes.http,
                stamp=dt,
            )
        )
        server_hab.psr.parse(ims=msgs)

    server_org = connecting.Organizer(hby=server_hby)

    # Create the environment and identifier for the sentinel
    sentinel_hby = habbing.Habery(name=sentinel_name, base=args.base, temp=False, **kwa)
    if not (sentinel_hab := sentinel_hby.habByName(sentinel_alias)):
        sentinel_hab = sentinel_hby.makeHab(
            name=sentinel_alias,
            transferable=True,
            icount=1,
            isith="1",
            ncount=1,
            nsith="1",
            toad=0,
        )

    if not (watcher_hab := server_hby.habByName(watcher_alias)):
        watcher_hab = server_hby.makeHab(
            name=watcher_alias,
            transferable=False,
        )


    sentinel_org = connecting.Organizer(hby=sentinel_hby)

    response = requests.get(config.root_oobi)
    server_hab.psr.parse(ims=response.content)
    sentinel_hab.psr.parse(ims=response.content)

    response = requests.get(config.api_oobi)
    server_hab.psr.parse(ims=response.content)
    sentinel_hab.psr.parse(ims=response.content)

    server_hab.kvy.processEscrows()
    sentinel_hab.kvy.processEscrows()

    if config.root_aid not in server_hby.kevers or config.api_aid not in server_hby.kevers:
        raise ConfigurationError(
            "Unable to resolve healthKERI root identifiers. Please check your configuration"
        )

    kel = sentinel_hab.replyToOobi(sentinel_hab.pre, role=kering.Roles.controller)
    delegated_kel = server_hab.replyToOobi(server_hab.pre, role=kering.Roles.controller)

    # "aid", "name", "server_auth_code", "type"
    data = dict(
        aid=sentinel_hab.pre,
        delegated_aid=server_hab.pre,
        server_auth_code=args.auth_key,
        type="sentinel",
        number_of_witnesses=args.number_of_witnesses,
    )
    files = {
        "kel": ("output.bin", bytes(kel), "application/octet-stream"),
        "delegated_kel": ("output.bin", bytes(delegated_kel), "application/octet-stream"),
        "doc": ("data.json", json.dumps(data), "application/json"),
    }

    response = requests.post(
        f"{config.unprotected_url}/account/teams/servers", files=files
    )

    if response.status_code != 201:  # type: ignore
        raise ValueError(f"Error registering server with healthKERI: {response.text}")


    data = response.json()

    # Process witnesses from the response
    witnesses = data.get('witnesses', [])
    witness_aids = []
    for witness in witnesses:
        witness_name = witness['name']
        witness_eid = witness['eid']
        witness_oobi = witness['oobi']

        witness_aids.append(witness_eid)

        logger.info(f"Loading OOBI for witness {witness_name} ({witness_eid})")

        # Load the witness OOBI
        try:
            oobi_response = requests.get(witness_oobi)
            oobi_response.raise_for_status()

            # Parse the OOBI for both server and sentinel
            server_hab.psr.parse(ims=oobi_response.content)
            sentinel_hab.psr.parse(ims=oobi_response.content)

            # Process escrows to resolve the witness
            server_hab.kvy.processEscrows()
            sentinel_hab.kvy.processEscrows()

            # Verify the witness AID is in the kevery
            if witness_eid not in server_hby.kevers:
                logger.warning(f"Witness {witness_name} ({witness_eid}) not resolved in server kevery")
                continue

            if witness_eid not in sentinel_hby.kevers:
                logger.warning(f"Witness {witness_name} ({witness_eid}) not resolved in sentinel kevery")
                continue

            # Create contact for the witness in both haberies
            server_org.set(witness_eid, "alias", witness_name)
            sentinel_org.set(witness_eid, "alias", witness_name)

            logger.info(f"Successfully added witness {witness_name} as contact")

        except Exception as e:
            raise Exception(f"Error processing witness {witness_name}: {e}")

    # Now create a rotation event with the new witnesses and None for Toad so ample is used to calculate.
    msg = server_hab.rotate(isith="1", ncount=1, nsith="1", adds=witness_aids, toad=None)

    # Get the full KEL from server_hab
    kel = server_hab.replyToOobi(server_hab.pre, role=kering.Roles.controller)

    # Prepare multipart body with KEL and tags
    tags_data = dict(tags=[])
    files = {
        "kel": ("output.bin", bytes(kel), "application/octet-stream"),
        "doc": ("data.json", json.dumps(tags_data), "application/json"),
    }

    # Execute PUT request to update the server
    update_response = requests.put(
        f"{config.unprotected_url}/account/teams/servers/{sentinel_hab.pre}",
        files=files
    )

    if update_response.status_code != 204:
        raise ValueError(f"Error updating server with healthKERI: {update_response.text}")

    logger.info(f"Successfully updated server {server_alias} with witnesses and tags")

    print()
    print(f"Machine {server_alias} updated successfully with witnesses and tags, please approve in Locksmith to continue")
    print(f"    Delegated Server {server_alias}: {server_hab.pre}")
    print(f"    healthKERI Account {sentinel_alias}: {sentinel_hab.pre}")
    print(f"    Watcher {watcher_alias}: {watcher_hab.pre}")
    print()