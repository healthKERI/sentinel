# -*- coding: utf-8 -*-
"""
sentinel.app.sentineling module

"""

from typing import List

from kept.hk.configing import HealthKERIConfig
from kept.hk.essring import APIClient
from keri.app import habbing

from sentinel.core.eventing import sync_server_key_state
from sentinel.core.watching import WatchedAdjudicationPoller, ObvsSocketListener
from sentinel.db.basing import SentinelBaser


class UnsupportedOperation(Exception):
    pass


def setup_local(
    name: str, alias: str, base: str, bran: str, uxd: bool, port: int
) -> List:
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


async def setup_hk(
    name: str, alias: str, base: str, bran: str, uxd: bool, port: int
) -> List:
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
    sentinel_name = f"{name}-sentinel"
    sentinel_alias = f"{alias}-sentinel"

    services = list()
    hby = habbing.Habery(name=sentinel_name, base=base, bran=bran)
    hab = hby.habByName(sentinel_alias)
    if not hab:
        raise ValueError(
            f"Sentinel alias for '{alias}' not found in sentinel Habery '{name}'"
        )

    db = SentinelBaser(name=name, headDirPath=base)

    config = HealthKERIConfig.get_instance()
    essr = APIClient(url=config.protected_url, root=config.api_aid, hby=hby, hab=hab)

    await sync_server_key_state(name, alias, base, bran, essr)

    poller = WatchedAdjudicationPoller(hby=hby, essr=essr, db=db, poll_interval=15.0)

    services.append(poller)

    if uxd:
        socket_path = f"/tmp/sentinel_{hab.pre}.sock"
        socket_listener = ObvsSocketListener(
            hby=hby, essr=essr, db=db, socket_path=socket_path, poll_interval=0.5
        )
        services.append(socket_listener)

    return services
