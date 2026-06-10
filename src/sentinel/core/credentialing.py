# -*- encoding: utf-8 -*-

"""
Sentinel
sentinel.core.credentialing package

"""

import asyncio

from keri.core import serdering, parsing
from keri.db import dbing
from keri import help
from keri.vdr import verifying

from sentinel.core import filing
from sentinel.core.authing import RequestAuth, Authenticater

logger = help.ogler.getLogger()


class CredentialLoader:
    """
    Manages credential loading and verification from a registrar service.

    The CredentialLoader monitors watched identifiers for credential issuance events
    and automatically retrieves, verifies, and exports credentials from a configured
    registrar service. It searches through Key Event Log (KEL) entries to identify
    credential seals and loads the corresponding credentials with retry logic and
    exponential backoff.

    This class integrates with KERI infrastructure components including the habery
    (key event log), registry (credential registry), verifier (credential verification),
    and parser (CESR message parsing) to provide end-to-end credential management.
    """

    def __init__(self, hby, hab, rgy, export_dir, registrar_url):
        """
        Initialize the CredentialLoader withhabery, registry, and configuration.

        Sets up the credential loading infrastructure including verifier and parser
        instances for processing credentials from a registrar service.

        Parameters:
            hby: Habery instance containing the key event log and database
            hab: Hab instance for credential verification and signing
            rgy: Registry instance for managing credential registry operations
            export_dir: Directory path where exported credentials will be stored
            registrar_url: Base URL of the registrar service for credential retrieval

        Attributes:
            hby: The habery instance
            hab: The hab instance for credential verification and signing
            rgy: The registry instance
            verifier: Verifier instance for credential verification
            psr: Parser instance for parsing credential and key event data
            export_dir: Directory path for credential exports
            registrar_url: URL of the registrar service
        """
        self.hby = hby
        self.hab = hab
        self.rgy = rgy
        self.verifier = verifying.Verifier(hby=self.hby, reger=self.rgy.reger)
        self.psr = parsing.Parser(kvy=self.hby.kvy, tvy=self.rgy.tvy, vry=self.verifier)
        authn = Authenticater(hab=self.hab, agent=None)
        self.auth = RequestAuth(authn)

        self.export_dir = export_dir
        self.registrar_url = registrar_url

    async def search_for_credentials(self, pre, local_sn, remote_sn):
        """
        Search for and load credentials from events between local and remote sequence numbers.

        Iterates through all Key Event Log (KEL) entries between the local and remote
        sequence numbers, extracts credential seals from each event, and attempts to
        load those credentials from the registrar service.

        Args:
            pre: The prefix (AID) of the watched identifier
            local_sn: The local sequence number (starting point, inclusive)
            remote_sn: The remote sequence number (ending point, inclusive)
        """

        for sn in range(local_sn, remote_sn + 1):
            pdig = self.hby.db.getKeLast(dbing.snKey(pre, sn))
            if not pdig:
                continue

            evt_key = dbing.dgKey(pre, bytes(pdig))  # get message
            raw = self.hby.db.getEvt(key=evt_key)
            serder = serdering.SerderKERI(raw=bytes(raw))
            for seal in serder.seals:
                await self._load_credential(seal)

    async def _load_credential(self, seal: dict):
        """
        Load a credential from the registrar with exponential backoff.

        Tries to load a credential from the registrar URL up to 10 times,
        using exponential backoff between attempts (1s, 2s, 4s, 8s, etc.).

        Args:
            seal: The seal representing a possible credential issuance

        Returns:
            The response if successful, None otherwise
        """
        if seal["s"] != "0":
            logger.info(f"Seal {seal} is not an issuance")
            return

        credential_said = seal["i"]
        if self.rgy.reger.creds.get(keys=(credential_said,)) is not None:
            logger.info(f"Credential {credential_said} already exists.")
            return

        import httpx

        base_delay = 1.0  # Start with 1 second
        max_attempts = 6

        url = (
            f"{self.registrar_url}/credential/{credential_said}?registry=true&tel=true"
        )

        async with httpx.AsyncClient() as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(
                        f"_load_credential: Attempt {attempt}/{max_attempts} for {credential_said}"
                    )

                    response = await client.get(url)

                    if response.status_code == 200:
                        logger.info(
                            f"_load_credential: Successfully loaded credential {credential_said}"
                        )

                        credential_data = response.content
                        self.psr.parse(credential_data)
                        self.psr.kvy.processEscrows()
                        self.rgy.tvy.processEscrows()
                        self.verifier.processEscrows()

                        # Export credential to filesystem
                        try:
                            if (
                                self.rgy.reger.creds.get(keys=(credential_said,))
                                is not None
                            ):
                                await filing.export_credential(
                                    rgy=self.rgy,
                                    credential_said=credential_said,
                                    export_dir=self.export_dir,
                                )
                        except Exception as e:
                            logger.error(
                                f"WatchedAdjudicationPoller: Failed to export credential for {credential_said}: {e}"
                            )

                        return
                    else:
                        reg_url = f"{self.registrar_url}/registry/{credential_said}"
                        response = await client.get(reg_url)

                        if response.status_code == 200:
                            logger.info(
                                f"_load_credential: Anchor said {credential_said} is a registry"
                            )
                            return

                        logger.warning(
                            f"_load_credential: Attempt {attempt} failed with status {response.status_code}"
                        )
                except Exception as e:
                    logger.error(
                        f"_load_credential: Attempt {attempt} raised exception: {e}"
                    )

                # If this wasn't the last attempt, wait before retrying
                if attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.debug(f"_load_credential: Waiting {delay}s before retry")
                    await asyncio.sleep(delay)

        logger.error(
            f"_load_credential: Failed to load credential {credential_said} after {max_attempts} attempts"
        )
