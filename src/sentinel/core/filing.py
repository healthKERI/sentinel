# -*- encoding: utf-8 -*-
"""
sentinel.core.filing module

Functions and services for exporting KELs, TELs and Credentials to
CESR format in files and directories.

"""

import logging
from pathlib import Path

from keri import kering
from keri.app.habbing import Habery

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
        hab = hby.habByPre(aid)
        if not hab:
            logger.error(f"KEL Export: Habitat not found for {aid}")
            return False

        # Generate CESR stream for the KEL
        kel_bytes = hab.replyToOobi(aid, role=kering.Roles.controller)

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
