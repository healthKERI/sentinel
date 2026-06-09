# -*- coding: utf-8 -*-
"""
sentinel.app.sentineling module

"""

from typing import List

from kept.hk.configing import HealthKERIConfig
from kept.hk.essring import APIClient
from keri.app import habbing
from keri import help
from keri.vdr import credentialing

from sentinel.core.eventing import sync_server_key_state
from sentinel.core.oobiing import Oobiery
from sentinel.core.watching import WatchedAdjudicationPoller, ObvsSocketListener
from sentinel.core.witnessing import LocalSocketListener
from sentinel.db.basing import SentinelBaser

logger = help.ogler.getLogger()


class UnsupportedOperation(Exception):
    pass


async def setup_local(
    name: str,
    alias: str,
    base: str,
    bran: str,
    uxd: bool,
    export_dir: str = "/usr/local/sentinel",
    registrar_url: str | None = None,
) -> List:
    """
    Setup sentinel watcher configuration for KERI local watching.

    Configures a sentinel instance that monitors KERI events using direct witness querying.

    Parameters:
        name: The name of the sentinel instance
        alias: The alias identifier for the sentinel
        base: The base directory path for sentinel data storage
        bran: The passcode for the sentinel instance
        uxd: Flag indicating whether to use Unix domain socket
        export_dir: Directory for exporting CESR files (default: /usr/local/sentinel)
        registrar_url: URL for Registrar if available

    Returns:
        List: A list of configured services for the sentinel instance

    """
    from sentinel.core.witnessing import Watcher

    services = list()

    # Create Habery for managing identifiers
    hby = habbing.Habery(name=name, base=base, bran=bran)
    hab = hby.habByName(alias)
    if hab is None:
        hab = hby.makeHab(name=alias, transferable=False)

    logger.info(f"Local watcher AID: {hab.pre}")

    # Create credential regery support
    rgy = credentialing.Regery(hby=hby, name=name, base=base)

    # Create database for watcher-specific data
    db = SentinelBaser(name=name, headDirPath=base)

    # Create local Watcher for direct witness querying
    watcher = Watcher(
        db=db,
        hby=hby,
        hab=hab,
        rgy=rgy,
        export_dir=export_dir,
        registrar_url=registrar_url,
    )
    services.append(watcher)

    oobiery = Oobiery(hby=hby, rvy=watcher.rvy)
    services.append(oobiery)

    # Initialize watched identifiers on startup
    if registrar_url:
        logger.info("Running startup adjudication and credential scan (local mode)")
        from sentinel.app import startup

        await startup.initialize_watched_credentials(
            hby=hby,
            hab=hab,
            rgy=rgy,
            db=db,
            export_dir=export_dir,
            registrar_url=registrar_url,
            essr=None,  # Local mode doesn't use essr
        )
    else:
        logger.info("No registrar URL configured, skipping credential scan")

    # Optional: Unix domain socket listener for real-time updates
    if uxd:
        socket_path = f"/tmp/sentinel_{hab.pre}.sock"
        socket_listener = LocalSocketListener(
            hby=hby, watcher=watcher, db=db, socket_path=socket_path, poll_interval=0.5
        )
        services.append(socket_listener)

    return services


async def setup_hk(
    name: str,
    alias: str,
    base: str,
    bran: str,
    uxd: bool,
    export_dir: str,
    registrar_url: str | None = None,
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
        export_dir: Directory for exporting CESR files
        registrar_url: URL for credential registrar

    Returns:
        List: A list of configured task services for the sentinel instance

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

    rgy = credentialing.Regery(hby=hby, name=name, base=base)
    db = SentinelBaser(name=name, headDirPath=base)

    config = HealthKERIConfig.get_instance()
    essr = APIClient(url=config.protected_url, root=config.api_aid, hby=hby, hab=hab)

    await sync_server_key_state(name, alias, base, bran, essr)

    poller = WatchedAdjudicationPoller(
        hby=hby,
        rgy=rgy,
        essr=essr,
        db=db,
        poll_interval=15.0,
        export_dir=export_dir,
        registrar_url=registrar_url,
    )

    services.append(poller)

    # Initialize watched identifiers on startup
    logger.info("Running startup adjudication and credential scan (healthKERI mode)")
    from sentinel.app import startup

    await startup.initialize_watched_credentials(
        hby=hby,
        hab=hab,
        rgy=rgy,
        db=db,
        export_dir=export_dir,
        registrar_url=registrar_url,
        essr=essr,
    )

    if uxd:
        socket_path = f"/tmp/sentinel_{hab.pre}.sock"
        socket_listener = ObvsSocketListener(
            hby=hby,
            essr=essr,
            db=db,
            socket_path=socket_path,
            poll_interval=0.5,
            registrar_url=registrar_url,
            export_dir=export_dir,
        )
        services.append(socket_listener)

    return services
