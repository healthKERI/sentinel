# -*- encoding: utf-8 -*-
"""
KERI
senitnel.app.cli.commands module

Initialize the Sentinel server using the provided auth_key
"""

import argparse

from keri import core, kering
from keri import help
from keri.app import habbing
from keri.app.keeping import Algos
from keri.core import parsing

from sentinel.core.initializing import SentinelConfig
from sentinel.core.oobiing import load_oobi
from sentinel.framework.connecting import connect_to_healthkeri

logger = help.ogler.getLogger()

parser = argparse.ArgumentParser(description="Initialize a new Sentinel instance.")
parser.set_defaults(handler=lambda args: up(args))
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
    required=False,
    help="The auth-key used to initialize this server with your healthKERI netmap",
)
parser.add_argument(
    "--local",
    action="store_true",
    default=False,
    help="Enable local mode instead of healthKERI SaaS mode",
)
parser.add_argument(
    "--issuer-aid",
    required=True,
    help="The AID of the issuer",
)
parser.add_argument(
    "--issuer-oobi",
    required=True,
    help="The OOBI URL of the issuer",
)
parser.add_argument(
    "--registrar-oobi",
    required=False,
    help="The OOBI URL of the registrar (required for local mode)",
)
parser.add_argument(
    "--registrar-aid",
    required=False,
    help="The AID of the registrar (required for local mode)",
)
parser.add_argument(
    "--registrar-url",
    required=False,
    help="The URL of the registrar (required for local mode)",
)
parser.add_argument(
    "--sentinel-config-path",
    required=False,
    help="Path to save the sentinel configuration file",
)
parser.add_argument(
    "--log-level",
    default="INFO",
    help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)


def up(args):
    server_name = args.name
    server_alias = args.alias

    sentinel_name = f"{server_name}-sentinel"
    sentinel_alias = f"{server_alias}-sentinel"

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
        )

    # Create the environment and identifier for the sentinel
    sentinel_hby = habbing.Habery(name=sentinel_name, base=args.base, temp=False, **kwa)
    if not (sentinel_hab := sentinel_hby.habByName(sentinel_alias)):
        sentinel_hab = sentinel_hby.makeHab(
            name=sentinel_alias,
            transferable=not args.local,
            icount=1,
            isith="1",
            ncount=1,
            nsith="1",
            toad=0,
        )

    sentinel_kel = sentinel_hab.replyToOobi(
        sentinel_hab.pre, role=kering.Roles.controller
    )
    server_hby.psr.parse(sentinel_kel)
    server_kel = server_hab.replyToOobi(server_hab.pre, role=kering.Roles.controller)
    sentinel_hby.psr.parse(server_kel)

    load_oobi(hby=server_hby, oobi=args.issuer_oobi, alias="issuer")
    load_oobi(hby=sentinel_hby, oobi=args.issuer_oobi, alias="issuer")

    sentinel_config = SentinelConfig()
    sentinel_config.name = sentinel_name
    sentinel_config.alias = sentinel_alias
    sentinel_config.server_name = server_name
    sentinel_config.server_alias = server_alias
    sentinel_config.bran = args.bran
    sentinel_config.base = args.base
    sentinel_config.uxd = True
    sentinel_config.local = args.local
    sentinel_config.export_dir = f"/usr/local/var/sentinel/{args.name}"

    sentinel_config.issuer.aid = args.issuer_aid
    sentinel_config.issuer.oobi = args.issuer_oobi

    if args.local:
        sentinel_config.registrar.aid = args.registrar_aid
        sentinel_config.registrar.oobi = args.registrar_oobi
        sentinel_config.registrar.url = args.registrar_url
    else:
        connect_to_healthkeri(
            server_name=server_alias, sentinel_hab=sentinel_hab, auth_key=args.auth_key
        )

    if args.sentinel_config_path:
        sentinel_config.save(args.sentinel_config_path)
    else:
        sentinel_config.save(f"/etc/sentinel/{args.name}.yaml")

    print()
    print(
        f"Machine {server_alias} updated successfully with witnesses and tags, please approve in Locksmith to continue"
    )
    print(f"    Server {server_alias}: {server_hab.pre}")
    print(f"    healthKERI Account {sentinel_alias}: {sentinel_hab.pre}")
    print()
