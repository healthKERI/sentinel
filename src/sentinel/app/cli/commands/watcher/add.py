# -*- encoding: utf-8 -*-
"""
KERI
sentinel.app.cli.commands module

"""

import argparse

from keri import help
from keri.app import connecting
from keri.app.cli.common import existing

from sentinel.framework.watching import LocalWatcherConnector

logger = help.ogler.getLogger()

parser = argparse.ArgumentParser(
    description="Add AID or Alias to list of AIDs for a watcher to watch"
)
parser.set_defaults(handler=lambda args: add(args))

parser.add_argument(
    "--name",
    "-n",
    help="keystore name and file location of KERI keystore",
    required=True,
)
parser.add_argument(
    "--alias",
    "-a",
    help="human readable alias for the identifier to whom the credential was issued",
    required=True,
)
parser.add_argument(
    "--base",
    "-b",
    help="additional optional prefix to file location of KERI keystore",
    required=False,
    default="",
)
parser.add_argument(
    "--passcode",
    "-p",
    help="22 character encryption passcode for keystore (is not saved)",
    dest="bran",
    default=None,
)  # passcode => bran
parser.add_argument(
    "--watcher", "-w", help="the watcher AID or alias to add to", required=True
)
parser.add_argument("--watched", "-W", help="the watched AID or alias to add")
parser.add_argument("--oobi", "-o", help="the OOBI for the watched AID")


def add(args):
    """Command line handler for adding an aid to a watcher's list of AIds to watch

    Parameters:
        args(Namespace): parsed command line arguments

    """
    with existing.existingHab(args.name, args.alias, args.base, args.bran) as (
        hby,
        hab,
    ):
        org = connecting.Organizer(hby=hby)
        watr = ""
        if args.watcher in hby.kevers:
            watr = args.watcher
        else:
            contacts = org.find("alias", args.watcher)
            for contact in contacts:
                if contact["alias"] == args.watcher:
                    watr = contact["id"]

        if not watr:
            raise ValueError(f"unknown watcher {args.watcher}")

        watd = ""
        if args.watched in hby.kevers:
            watd = args.watched
        else:
            contacts = org.find("alias", args.watched)
            for contact in contacts:
                if contact["alias"] == args.watched:
                    watd = contact["id"]

        if not watd:
            raise ValueError(f"unknown watched {args.watched}")

        local_watcher_connector = LocalWatcherConnector(hby, hab, watr)
        local_watcher_connector.watch(watd, args.oobi)
