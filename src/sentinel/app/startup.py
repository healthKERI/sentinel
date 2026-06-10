# -*- coding: utf-8 -*-
"""
sentinel.app.startup module

Startup initialization logic for adjudicating watched identifiers and scanning for credentials.
"""

import asyncio

from kept.hk.essring import APIClient
from keri import help, core
from keri.app.habbing import Habery, Hab
from keri.vdr.credentialing import Regery

from sentinel.core.credentialing import CredentialLoader
from sentinel.core.remoting import sync_watched_identifier
from sentinel.core.witnessing import Sentinel
from sentinel.db.basing import SentinelBaser

logger = help.ogler.getLogger()

# Timeout for entire startup process (5 minutes)
STARTUP_TIMEOUT = 300


async def initialize_watched_credentials(
    hby: Habery,
    hab: Hab,
    rgy: Regery,
    db: SentinelBaser,
    export_dir: str,
    registrar_url: str | None,
    essr: APIClient | None = None,
) -> None:
    """
    Run adjudication and credential scanning for all watched identifiers on startup.

    For each watched identifier:
    1. Adjudicate key state (ensure we have latest KEL)
    2. Scan entire KEL (sn=0 to current) for credential anchors
    3. Load any credentials not already in registry

    Parameters:
        hby: Habery instance containing the key event log and database
        hab: Hab instance for the sentinel
        rgy: Registry instance for managing credential registry operations
        db: SentinelBaser database instance
        export_dir: Directory path where exported credentials will be stored
        registrar_url: Base URL of the registrar service (required for credential loading)
        essr: ESSR API client for healthKERI mode (None for local mode)
    """
    try:
        # Use essr to determine mode
        mode = "healthKERI" if essr else "local"
        logger.info(f"Startup: Running initialization in {mode} mode")

        # Get all watched identifiers from obvs database
        watched_oids = []
        for (cid, aid, oid), observed in hby.db.obvs.getItemIter(keys=(hab.pre,)):
            if observed.enabled:
                watched_oids.append((cid, oid))

        if not watched_oids:
            logger.info("Startup: No watched identifiers found")
            return

        logger.info(f"Startup: Found {len(watched_oids)} watched identifiers")

        # Process watched identifiers with overall timeout
        success_count = 0
        error_count = 0

        async with asyncio.timeout(STARTUP_TIMEOUT):
            if essr:
                # HealthKERI mode: Process in parallel (3-5 at a time)
                success_count, error_count = await _process_hk_mode(
                    hby=hby,
                    hab=hab,
                    rgy=rgy,
                    essr=essr,
                    watched_oids=watched_oids,
                    export_dir=export_dir,
                    registrar_url=registrar_url,
                )
            else:
                # Local mode: Process sequentially
                success_count, error_count = await _process_local_mode(
                    hby=hby,
                    hab=hab,
                    rgy=rgy,
                    db=db,
                    watched_oids=watched_oids,
                    export_dir=export_dir,
                    registrar_url=registrar_url,
                )

        logger.info(
            f"Startup: Initialization complete - processed {success_count}/{len(watched_oids)} identifiers "
            f"(errors: {error_count})"
        )

    except asyncio.TimeoutError:
        logger.error(
            f"Startup: Initialization timed out after {STARTUP_TIMEOUT} seconds"
        )
    except Exception as e:
        logger.exception(f"Startup: Unexpected error during initialization: {e}")


async def _process_local_mode(
    hby: Habery,
    hab: Hab,
    rgy: Regery,
    db: SentinelBaser,
    watched_oids: list[tuple[str, str]],
    export_dir: str,
    registrar_url: str | None,
) -> tuple[int, int]:
    """
    Process watched identifiers in local mode (sequential).

    Returns:
        Tuple of (success_count, error_count)
    """
    success_count = 0
    error_count = 0

    for cid, oid in watched_oids:
        try:
            logger.info(f"Startup: Processing {oid}...")

            cur_number = db.watched_scan_index.get(keys=(oid,))
            current_sn = 0 if cur_number is None else cur_number.num

            # Adjudicate key state
            if not await adjudicate_local(
                hby=hby,
                hab=hab,
                rgy=rgy,
                db=db,
                oid=oid,
                cid=cid,
                export_dir=export_dir,
                registrar_url=registrar_url,
            ):
                logger.warning(f"Startup: Failed to adjudicate {oid}")
                error_count += 1
                continue

            # Scan KEL for credentials (only if registrar_url is configured)
            if registrar_url:
                credential_count = await scan_kel_for_credentials(
                    hby=hby,
                    hab=hab,
                    rgy=rgy,
                    oid=oid,
                    pre_sn=current_sn,
                    export_dir=export_dir,
                    registrar_url=registrar_url,
                )

                db.watched_scan_index.pin(
                    keys=(oid,), value=core.Number(num=credential_count)
                )
                logger.info(
                    f"Startup: Completed initialization for {oid} ({credential_count} credentials processed)"
                )
            else:
                logger.info(
                    f"Startup: Completed initialization for {oid} (credential scanning skipped - no registrar URL)"
                )

            success_count += 1

        except Exception as e:
            logger.exception(f"Startup: Error processing {oid}: {e}")
            error_count += 1
            continue

    return success_count, error_count


async def _process_hk_mode(
    hby: Habery,
    hab: Hab,
    rgy: Regery,
    essr: APIClient,
    watched_oids: list[tuple[str, str]],
    export_dir: str,
    registrar_url: str | None,
) -> tuple[int, int]:
    """
    Process watched identifiers in healthKERI mode (parallel, 5 at a time).

    Returns:
        Tuple of (success_count, error_count)
    """
    success_count = 0
    error_count = 0

    # Process 5 identifiers at a time
    batch_size = 5
    for i in range(0, len(watched_oids), batch_size):
        batch = watched_oids[i : i + batch_size]
        tasks = []

        for cid, oid in batch:
            tasks.append(
                _process_single_hk_identifier(
                    hby=hby,
                    hab=hab,
                    rgy=rgy,
                    essr=essr,
                    oid=oid,
                    export_dir=export_dir,
                    registrar_url=registrar_url,
                )
            )

        # Run batch in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and errors
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
            elif result:
                success_count += 1
            else:
                error_count += 1

    return success_count, error_count


async def _process_single_hk_identifier(
    hby: Habery,
    hab: Hab,
    rgy: Regery,
    essr: APIClient,
    oid: str,
    export_dir: str,
    registrar_url: str | None,
) -> bool:
    """
    Process a single watched identifier in healthKERI mode.

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Startup: Processing {oid}...")

        # Adjudicate key state
        if not await adjudicate_hk(hby=hby, essr=essr, oid=oid):
            logger.warning(f"Startup: Failed to adjudicate {oid}")
            return False

        # Scan KEL for credentials (only if registrar_url is configured)
        if registrar_url:
            credential_count = await scan_kel_for_credentials(
                hby=hby,
                hab=hab,
                rgy=rgy,
                oid=oid,
                pre_sn=0,
                export_dir=export_dir,
                registrar_url=registrar_url,
            )
            logger.info(
                f"Startup: Completed initialization for {oid} ({credential_count} credentials processed)"
            )
        else:
            logger.info(
                f"Startup: Completed initialization for {oid} (credential scanning skipped - no registrar URL)"
            )

        return True

    except Exception as e:
        logger.exception(f"Startup: Error processing {oid}: {e}")
        return False


async def adjudicate_local(
    hby: Habery,
    hab: Hab,
    rgy: Regery,
    db: SentinelBaser,
    oid: str,
    cid: str,
    export_dir: str,
    registrar_url: str | None,
) -> bool:
    """
    Adjudicate key state for a watched identifier in local mode.

    Creates a temporary Sentinel instance and calls watch() to query witnesses.

    Parameters:
        hby: Habery instance
        hab: Hab instance for the sentinel
        rgy: Registry instance
        db: SentinelBaser database instance
        oid: Object identifier being watched
        cid: Controller identifier
        export_dir: Directory for exporting CESR files
        registrar_url: URL for Registrar if available

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.debug(f"Startup: Adjudicating {oid} (local mode)")

        # Check if identifier exists in kevers
        if oid not in hby.kevers:
            logger.warning(f"Startup: {oid} not in kevers, skipping adjudication")
            return False

        # Create temporary Sentinel instance
        sentinel = Sentinel(
            hby=hby,
            hab=hab,
            rgy=rgy,
            oid=oid,
            cid=cid,
            db=db,
            export_dir=export_dir,
            registrar_url=registrar_url,
        )

        # Run watch with timeout (30 seconds per identifier)
        async with asyncio.timeout(30):
            await sentinel.watch()

        logger.debug(f"Startup: Successfully adjudicated {oid}")
        return True

    except asyncio.TimeoutError:
        logger.error(f"Startup: Timeout adjudicating {oid}")
        return False
    except Exception as e:
        logger.exception(f"Startup: Error adjudicating {oid}: {e}")
        return False


async def adjudicate_hk(
    hby: Habery,
    essr: APIClient,
    oid: str,
) -> bool:
    """
    Adjudicate key state for a watched identifier in healthKERI mode.

    Calls sync_watched_identifier() to get latest KEL from healthKERI.

    Parameters:
        hby: Habery instance
        essr: ESSR API client
        oid: Object identifier being watched

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.debug(f"Startup: Adjudicating {oid} (healthKERI mode)")

        # Sync watched identifier
        result = await sync_watched_identifier(hby=hby, essr=essr, aid=oid)

        if result.get("success"):
            logger.debug(f"Startup: Successfully adjudicated {oid}")
            return True
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Startup: Failed to adjudicate {oid}: {error}")
            return False

    except Exception as e:
        logger.exception(f"Startup: Error adjudicating {oid}: {e}")
        return False


async def scan_kel_for_credentials(
    hby: Habery,
    hab: Hab,
    rgy: Regery,
    oid: str,
    pre_sn: int,
    export_dir: str,
    registrar_url: str,
) -> int:
    """
    Scan entire KEL for credential anchors and load credentials.

    Parameters:
        hby: Habery instance
        hab: Hab instance for the sentinel
        rgy: Registry instance
        oid: Object identifier being watched
        pre_sn: Previous sequence number of the local key state
        export_dir: Directory for exporting CESR files
        registrar_url: URL for Registrar

    Returns:
        Number of credentials found (whether loaded or already existed)
    """
    try:
        # Check if identifier exists in kevers
        if oid not in hby.kevers:
            logger.warning(f"Startup: {oid} not in kevers, skipping credential scan")
            return 0

        # Get current sequence number
        current_sn = hby.kevers[oid].sn

        # Skip if no events to scan
        if current_sn < 0:
            logger.info(f"Startup: {oid} has no events to scan")
            return 0

        logger.info(f"Startup: Scanning KEL for {oid} (sn={pre_sn} to sn={current_sn})")

        # Create CredentialLoader and scan KEL
        credential_loader = CredentialLoader(
            hby=hby,
            hab=hab,
            rgy=rgy,
            export_dir=export_dir,
            registrar_url=registrar_url,
        )

        # Scan from sn=0 to current_sn (search_for_credentials uses local_sn + 1, so pass -1 to start from 0)
        await credential_loader.search_for_credentials(
            pre=oid,
            local_sn=pre_sn,  # Will scan from sn=0 (local_sn + 1)
            remote_sn=current_sn,
        )

        # Note: We don't track the exact count of credentials found
        # The CredentialLoader logs each credential it processes
        return current_sn + 1  # Return number of events scanned as proxy

    except Exception as e:
        logger.exception(f"Startup: Error scanning KEL for {oid}: {e}")
        return 0
