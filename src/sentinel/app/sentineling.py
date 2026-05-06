# -*- coding: utf-8 -*-
"""
sentinel.app.sentineling module

"""
from typing import List

from kept.hk.configing import HealthKERIConfig
from kept.hk.essring import APIClient
from keri.app import habbing

from sentinel.core.watching import WatchedAdjudicationPoller
from sentinel.db.basing import SentinelBaser


class UnsupportedOperation(Exception):
    pass


def setup_local(name: str, alias: str, base: str, bran: str, uxd: bool, port: int) -> List:
    """
    Setup sentinel watcher configuration for KERI local watching.

    Configures a sentinel instance that monitors KERI events using either the healthKERI
    Watcher Network or direct witness querying.

    Parameters:
        name: The name of the sentinel instance
        alias: The alias identifier for the sentinel
        base: The base directory path for sentinel data storage
        bran: The passcode for the sentinel instance
        uxd: Flag indicating whether to use Unix domain socket
        port: The port number for network communication

    Returns:
        List: A list of configured doers for the sentinel instance

    """
    raise UnsupportedOperation("Local watcher configuration is not supported yet")


def setup_hk(name: str, alias: str, base: str, bran: str, uxd: bool, port: int) -> List:
    """
    Setup sentinel watcher configuration for KERI local watching.

    Configures a sentinel instance that monitors KERI events using either the healthKERI
    Watcher Network or direct witness querying.

    Parameters:
        name: The name of the sentinel instance
        alias: The alias identifier for the sentinel
        base: The base directory path for sentinel data storage
        bran: The passcode for the sentinel instance
        uxd: Flag indicating whether to use Unix domain socket
        port: The port number for network communication

    Returns:
        List: A list of configured doers for the sentinel instance

    """
    hby = habbing.Habery(name=name, base=base, bran=bran)
    hab = hby.habByName(alias)
    if not hab:
        raise ValueError(f"Alias '{alias}' not found in Habery '{name}'")

    db = SentinelBaser(name=name, headDirPath=base)

    config = HealthKERIConfig.get_instance()
    essr = APIClient(
        url=config.protected_url,
        root=config.api_aid,
        hby=hby,
        hab=hab
    )

    poller = WatchedAdjudicationPoller(hby=hby, essr=essr, db=db, poll_interval=5.0, check_interval=5.0)

    return [poller]
