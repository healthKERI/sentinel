# -*- encoding: utf-8 -*-
"""
sentinel.core.filing module

Functions and services for exporting KELs, TELs and Credentials to
CESR format in files and directories.

"""

import logging
from pathlib import Path

from keri.app import signing
from keri.app.habbing import Habery
from keri.vdr.credentialing import Regery

logger = logging.getLogger(__name__)


async def export_kel(hby: Habery, aid: str, export_dir: str) -> bool:
    """
    Export the full Key Event Log (KEL) for an identifier to CESR format.

    Args:
        hby: Habery instance with access to the identifier
        aid: The identifier's AID/prefix to export
        export_dir: Base directory for exports (e.g., /usr/local/sentinel)

    Returns:
        bool: True if successful, False otherwise

    The KEL will be written to: {export_dir}/kel/{aid}.cesr
    Directory structure is created if it doesn't exist.
    Existing files are overwritten with the latest KEL state.
    """
    try:
        # Get the habitat for this identifier
        kever = hby.kevers.get(aid)
        if not kever:
            logger.error(f"KEL Export: Hab not found for {aid}")
            return False

        # Generate CESR stream for the KEL
        kel_bytes = bytearray()
        for msg in hby.db.cloneDelegation(kever=kever):
            kel_bytes.extend(msg)

        for msg in hby.db.clonePreIter(pre=aid):
            kel_bytes.extend(msg)

        # Create directory structure: {export_dir}/kel/
        kel_dir = Path(export_dir) / "kel"
        kel_dir.mkdir(parents=True, exist_ok=True)

        # Write to file: {aid}.cesr
        output_path = kel_dir / f"{aid}.cesr"
        with open(output_path, "wb") as f:
            f.write(bytes(kel_bytes))

        logger.info(f"KEL Export: Successfully wrote KEL for {aid} to {output_path}")
        return True

    except PermissionError as e:
        logger.error(f"KEL Export: Permission denied writing to {export_dir}: {e}")
        return False
    except OSError as e:
        logger.error(f"KEL Export: OS error writing KEL for {aid}: {e}")
        return False
    except Exception as e:
        logger.exception(f"KEL Export: Unexpected error exporting KEL for {aid}: {e}")
        return False


async def export_credential(rgy: Regery, credential_said: str, export_dir: str) -> bool:
    try:
        creder, *_ = rgy.reger.cloneCred(said=credential_said)
        if not creder:
            return False

        if creder.regi is not None:
            export_tel(rgy, creder.regi, export_dir)
            export_tel(rgy, creder.said, export_dir)

        chains = creder.edge if creder.edge is not None else {}
        saids = []
        for key, source in chains.items():
            if key == "d":
                continue

            if not isinstance(source, dict):
                continue

            saids.append(source["n"])

        for said in saids:
            await export_credential(rgy, said, export_dir)

        prefixer, seqner, saider = rgy.reger.cancs.get(keys=(creder.said,))

        # Create directory structure: {export_dir}/credential/
        cred_dir = Path(export_dir) / "credential"
        cred_dir.mkdir(parents=True, exist_ok=True)

        # Write to file: {aid}.cesr
        output_path = cred_dir / f"{creder.said}.cesr"
        if output_path.exists():
            logger.warning(
                f"KEL Export: Credential {creder.said} already exists at {output_path}"
            )
            return True

        with open(output_path, "wb") as f:
            f.write(signing.serialize(creder, prefixer, seqner, saider))

        return True

    except PermissionError as e:
        logger.error(f"KEL Export: Permission denied writing to {export_dir}: {e}")
        return False
    except OSError as e:
        logger.error(f"KEL Export: OS error writing KEL for {credential_said}: {e}")
        return False
    except Exception as e:
        logger.exception(
            f"KEL Export: Unexpected error exporting KEL for {credential_said}: {e}"
        )
        return False


def export_tel(rgy: Regery, regk, export_dir: str) -> bool:
    """
    Export the full Transaction Event Log (TEL) for a registry to CESR format.

    Args:
        rgy: Regery instance with access to the registry
        regk: The registry identifier/prefix to export
        export_dir: Base directory for exports (e.g., /usr/local/sentinel)

    Returns:
        bool: True if successful, False otherwise

    The TEL will be written to: {export_dir}/tel/{regk}.cesr
    Directory structure is created if it doesn't exist.
    Existing files are overwritten with the latest TEL state.
    """
    # Create directory structure: {export_dir}/tel/
    tel_dir = Path(export_dir) / "tel"
    tel_dir.mkdir(parents=True, exist_ok=True)

    # Write to file: {aid}.cesr
    output_path = tel_dir / f"{regk}.cesr"
    with open(output_path, "wb") as f:
        for msg in rgy.reger.clonePreIter(pre=regk):
            f.write(msg)

    return True
