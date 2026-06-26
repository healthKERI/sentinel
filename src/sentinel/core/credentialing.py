# -*- encoding: utf-8 -*-

"""
Sentinel
sentinel.core.credentialing package

"""

import asyncio

import httpx
from keri import help
from keri.core import parsing
from keri.vdr import verifying
from sentinel.core import filing
from sentinel.core.authing import RequestAuth, Authenticater

logger = help.ogler.getLogger()


class SaaSCredentialLoader:
    """
    SaaS-mode credential loader: uses ESSR to talk to hkweb's /registrar/ API.

    Mirrors the interface of CredentialLoader but uses the ESSR client instead of
    a plain HTTP registrar URL.
    """

    def __init__(self, hby, hab, rgy, export_dir, essr):
        self.hby = hby
        self.hab = hab
        self.rgy = rgy
        self.verifier = verifying.Verifier(hby=self.hby, reger=self.rgy.reger)
        self.psr = parsing.Parser(kvy=self.hby.kvy, tvy=self.rgy.tvy, vry=self.verifier)
        self.export_dir = export_dir
        self.essr = essr

    async def search_for_credentials(self, pre, current_sn):
        """
        Search hkweb for credentials issued by pre at or after current_sn.

        Retries with exponential backoff on 412 (platform not yet caught up).
        """
        base_delay = 5.0
        max_attempts = 6
        path = f"/registrar/credentials/search?issuer={pre}&issuer_sn={current_sn}"

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.essr.request(path=path, method="GET")
                if response.status_code == 200:
                    logger.info(
                        f"SaaSCredentialLoader: queried credentials for issuer {pre}"
                    )
                    saids = response.json().get("credentials", [])
                    await asyncio.gather(*[self._load_credential(said) for said in saids])
                    self.psr.kvy.processEscrows()
                    self.rgy.tvy.processEscrows()
                    self.verifier.processEscrows()
                    await asyncio.gather(*[self._save_credential(said) for said in saids])
                    return
                elif response.status_code == 412:
                    logger.info(
                        "SaaSCredentialLoader: hkweb not caught up to issuer_sn, retrying"
                    )
                else:
                    logger.error(
                        f"SaaSCredentialLoader: unexpected status {response.status_code} for issuer {pre}"
                    )
                    return
            except Exception as e:
                logger.error(f"SaaSCredentialLoader: attempt {attempt} error: {e}")

            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))
                logger.debug(f"SaaSCredentialLoader: waiting {delay}s before retry")
                await asyncio.sleep(delay)

    async def _load_credential(self, said):
        if self.rgy.reger.creds.get(keys=(said,)) is not None:
            logger.info(f"SaaSCredentialLoader: credential {said} already exists")
            return
        path = f"/registrar/credential/{said}?registry=true&tel=true"
        try:
            response = await self.essr.request(path=path, method="GET")
            if response.status_code == 200:
                self.psr.parse(response.content)
            else:
                logger.error(
                    f"SaaSCredentialLoader: failed to load {said}, status {response.status_code}"
                )
        except Exception as e:
            logger.error(f"SaaSCredentialLoader: error loading {said}: {e}")

    async def _save_credential(self, said):
        try:
            if self.rgy.reger.creds.get(keys=(said,)) is not None:
                await filing.export_credential(
                    rgy=self.rgy,
                    credential_said=said,
                    export_dir=self.export_dir,
                )
        except Exception as e:
            logger.error(
                f"SaaSCredentialLoader: failed to export credential {said}: {e}"
            )


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

    async def search_for_credentials(self, pre, current_sn):
        """
        Search for and load credentials from events between local and remote sequence numbers.

        Iterates through all Key Event Log (KEL) entries between the local and remote
        sequence numbers, extracts credential seals from each event, and attempts to
        load those credentials from the registrar service.

        Args:
            pre: The prefix (AID) of the watched identifier
            current_sn: The local sequence number of the AID to search (starting point, inclusive)
        """

        base_delay = 5.0  # Start with 1 second
        max_attempts = 6

        url = f"{self.registrar_url}/credentials/search?issuer={pre}&issuer_sn={current_sn}"

        async with httpx.AsyncClient() as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    response = await client.get(url)

                    if response.status_code == 200:
                        logger.info(
                            f"_load_credential: Successfully queried for issuer {pre} credentials"
                        )

                        credential_data = response.json()
                        saids = credential_data.get("credentials", [])

                        # Try to load and parse all the credentials in parallel
                        await asyncio.gather(
                            *[self._load_credential(said) for said in saids]
                        )

                        self.psr.kvy.processEscrows()
                        self.rgy.tvy.processEscrows()
                        self.verifier.processEscrows()

                        # Export all credentials to filesystem in parallel
                        await asyncio.gather(
                            *[self._save_credential(said) for said in saids]
                        )

                        return

                    elif response.status_code == 412:
                        logger.info(
                            "_load_credential: Registrar issuer not up to date, retrying"
                        )
                    else:
                        logger.error(
                            f"_load_credential: Unexpected status code {response.status_code} for issuer {pre}"
                        )
                        return

                except Exception as e:
                    logger.error(
                        f"_load_credential: Attempt {attempt} raised exception: {e}"
                    )

                # If this wasn't the last attempt, wait before retrying
                if attempt < max_attempts:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.debug(f"_load_credential: Waiting {delay}s before retry")
                    await asyncio.sleep(delay)

    async def _load_credential(self, credential_said):
        """
        Load a credential from the registrar with exponential backoff.

        Tries to load a credential from the registrar URL up to 10 times,
        using exponential backoff between attempts (1s, 2s, 4s, 8s, etc.).

        Args:
            credential_said: The said of the credential to load.

        Returns:
            The response if successful, None otherwise
        """
        if self.rgy.reger.creds.get(keys=(credential_said,)) is not None:
            logger.info(f"Credential {credential_said} already exists.")
            return

        base_delay = 1.0  # Start with 1 second
        max_attempts = 3

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
                        return

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

    async def _save_credential(self, said):
        try:
            if self.rgy.reger.creds.get(keys=(said,)) is not None:
                await filing.export_credential(
                    rgy=self.rgy,
                    credential_said=said,
                    export_dir=self.export_dir,
                )
        except Exception as e:
            logger.error(
                f"WatchedAdjudicationPoller: Failed to export credential for {said}: {e}"
            )
