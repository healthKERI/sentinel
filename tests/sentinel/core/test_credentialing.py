# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.core.credentialing module
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock, call

from sentinel.core.credentialing import CredentialLoader


class TestCredentialLoader(unittest.IsolatedAsyncioTestCase):
    """Test cases for CredentialLoader class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_hby = Mock()
        self.mock_hby.kvy = Mock()
        self.mock_hab = Mock()
        self.mock_hab.pre = "EHabPrefix123"
        self.mock_rgy = Mock()
        self.mock_rgy.reger = Mock()
        self.mock_rgy.reger.creds = Mock()
        self.mock_rgy.tvy = Mock()
        self.export_dir = "/tmp/test_export"
        self.registrar_url = "https://registrar.example.com"

    def test_credential_loader_initialization(self):
        """Test CredentialLoader initialization"""
        with patch(
            "sentinel.core.credentialing.verifying.Verifier"
        ) as mock_verifier_class:
            with patch(
                "sentinel.core.credentialing.parsing.Parser"
            ) as mock_parser_class:
                with patch("sentinel.core.credentialing.Authenticater"):
                    mock_verifier = Mock()
                    mock_parser = Mock()
                    mock_verifier_class.return_value = mock_verifier
                    mock_parser_class.return_value = mock_parser

                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    self.assertEqual(loader.hby, self.mock_hby)
                    self.assertEqual(loader.hab, self.mock_hab)
                    self.assertEqual(loader.rgy, self.mock_rgy)
                    self.assertEqual(loader.export_dir, self.export_dir)
                    self.assertEqual(loader.registrar_url, self.registrar_url)
                    self.assertEqual(loader.verifier, mock_verifier)
                    self.assertEqual(loader.psr, mock_parser)

    async def test_search_for_credentials_success(self):
        """Test successful credential search"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Mock HTTP response
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        "credentials": ["ESaid123", "ESaid456"]
                    }

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(return_value=mock_response)

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        with patch.object(
                            loader, "_load_credential", new_callable=AsyncMock
                        ) as mock_load:
                            with patch.object(
                                loader, "_save_credential", new_callable=AsyncMock
                            ) as mock_save:
                                loader.psr.kvy.processEscrows = Mock()
                                loader.rgy.tvy.processEscrows = Mock()
                                loader.verifier.processEscrows = Mock()

                                await loader.search_for_credentials(
                                    pre="EIssuerPrefix", current_sn=5
                                )

                                # Verify API call
                                expected_url = "https://registrar.example.com/credentials/search?issuer=EIssuerPrefix&issuer_sn=5"
                                mock_client.get.assert_called_once_with(expected_url)

                                # Verify load_credential called for each SAID
                                self.assertEqual(mock_load.call_count, 2)
                                mock_load.assert_any_call("ESaid123")
                                mock_load.assert_any_call("ESaid456")

                                # Verify escrow processing
                                loader.psr.kvy.processEscrows.assert_called_once()
                                loader.rgy.tvy.processEscrows.assert_called_once()
                                loader.verifier.processEscrows.assert_called_once()

                                # Verify save_credential called for each SAID
                                self.assertEqual(mock_save.call_count, 2)
                                mock_save.assert_any_call("ESaid123")
                                mock_save.assert_any_call("ESaid456")

    async def test_search_for_credentials_empty_list(self):
        """Test search with no credentials found"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Mock HTTP response with empty credentials list
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"credentials": []}

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(return_value=mock_response)

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        with patch.object(
                            loader, "_load_credential", new_callable=AsyncMock
                        ) as mock_load:
                            with patch.object(
                                loader, "_save_credential", new_callable=AsyncMock
                            ) as mock_save:
                                loader.psr.kvy.processEscrows = Mock()
                                loader.rgy.tvy.processEscrows = Mock()
                                loader.verifier.processEscrows = Mock()

                                await loader.search_for_credentials(
                                    pre="EIssuerPrefix", current_sn=5
                                )

                                # Verify load and save not called
                                mock_load.assert_not_called()
                                mock_save.assert_not_called()

    async def test_search_for_credentials_retry_on_412(self):
        """Test retry logic when registrar returns 412"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Mock HTTP responses - first 412, then 200
                    mock_response_412 = Mock()
                    mock_response_412.status_code = 412

                    mock_response_200 = Mock()
                    mock_response_200.status_code = 200
                    mock_response_200.json.return_value = {"credentials": ["ESaid123"]}

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(
                        side_effect=[mock_response_412, mock_response_200]
                    )

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        with patch.object(
                            loader, "_load_credential", new_callable=AsyncMock
                        ):
                            with patch.object(
                                loader, "_save_credential", new_callable=AsyncMock
                            ):
                                loader.psr.kvy.processEscrows = Mock()
                                loader.rgy.tvy.processEscrows = Mock()
                                loader.verifier.processEscrows = Mock()

                                with patch(
                                    "sentinel.core.credentialing.asyncio.sleep",
                                    new_callable=AsyncMock,
                                ) as mock_sleep:
                                    await loader.search_for_credentials(
                                        pre="EIssuerPrefix", current_sn=5
                                    )

                                    # Verify retry occurred
                                    self.assertEqual(mock_client.get.call_count, 2)
                                    # Verify sleep was called for exponential backoff
                                    mock_sleep.assert_called_once_with(5.0)

    async def test_search_for_credentials_unexpected_status(self):
        """Test handling of unexpected status code"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Mock HTTP response with unexpected status
                    mock_response = Mock()
                    mock_response.status_code = 500

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(return_value=mock_response)

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        with patch.object(
                            loader, "_load_credential", new_callable=AsyncMock
                        ) as mock_load:
                            await loader.search_for_credentials(
                                pre="EIssuerPrefix", current_sn=5
                            )

                            # Verify only one attempt made
                            self.assertEqual(mock_client.get.call_count, 1)
                            # Verify load not called
                            mock_load.assert_not_called()

    async def test_search_for_credentials_exception(self):
        """Test handling of exception during search"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(side_effect=Exception("Network error"))

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        with patch(
                            "sentinel.core.credentialing.asyncio.sleep",
                            new_callable=AsyncMock,
                        ) as mock_sleep:
                            await loader.search_for_credentials(
                                pre="EIssuerPrefix", current_sn=5
                            )

                            # Verify retries occurred (max 6 attempts)
                            self.assertEqual(mock_client.get.call_count, 6)
                            # Verify exponential backoff
                            self.assertEqual(mock_sleep.call_count, 5)

    async def test_load_credential_success(self):
        """Test successful credential load"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Credential does not exist yet
                    self.mock_rgy.reger.creds.get.return_value = None

                    # Mock HTTP response
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.content = b"credential_data"

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(return_value=mock_response)

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        loader.psr.parse = Mock()

                        await loader._load_credential("ESaid123")

                        # Verify API call
                        expected_url = "https://registrar.example.com/credential/ESaid123?registry=true&tel=true"
                        mock_client.get.assert_called_once_with(expected_url)

                        # Verify parse called with credential data
                        loader.psr.parse.assert_called_once_with(b"credential_data")

    async def test_load_credential_already_exists(self):
        """Test load when credential already exists"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Credential already exists
                    self.mock_rgy.reger.creds.get.return_value = Mock()

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock()

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        await loader._load_credential("ESaid123")

                        # Verify API call not made
                        mock_client.get.assert_not_called()

    async def test_load_credential_retry_on_exception(self):
        """Test retry logic on exception during load"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Credential does not exist
                    self.mock_rgy.reger.creds.get.return_value = None

                    # Mock exception then success
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.content = b"credential_data"

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(
                        side_effect=[Exception("Timeout"), mock_response]
                    )

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        loader.psr.parse = Mock()

                        with patch(
                            "sentinel.core.credentialing.asyncio.sleep",
                            new_callable=AsyncMock,
                        ) as mock_sleep:
                            await loader._load_credential("ESaid123")

                            # Verify retry occurred
                            self.assertEqual(mock_client.get.call_count, 2)
                            # Verify exponential backoff
                            mock_sleep.assert_called_once_with(1.0)

    async def test_load_credential_max_retries(self):
        """Test load fails after max retries"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Credential does not exist
                    self.mock_rgy.reger.creds.get.return_value = None

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(
                        side_effect=Exception("Persistent error")
                    )

                    with patch(
                        "sentinel.core.credentialing.httpx.AsyncClient"
                    ) as mock_client_class:
                        mock_client_instance = AsyncMock()
                        mock_client_instance.__aenter__.return_value = mock_client
                        mock_client_class.return_value = mock_client_instance

                        with patch(
                            "sentinel.core.credentialing.asyncio.sleep",
                            new_callable=AsyncMock,
                        ) as mock_sleep:
                            await loader._load_credential("ESaid123")

                            # Verify max attempts (3)
                            self.assertEqual(mock_client.get.call_count, 3)
                            # Verify exponential backoff called twice (not after last attempt)
                            self.assertEqual(mock_sleep.call_count, 2)
                            # Verify backoff intervals (1.0, 2.0)
                            mock_sleep.assert_has_calls([call(1.0), call(2.0)])

    async def test_save_credential_success(self):
        """Test successful credential save"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Credential exists
                    mock_cred = Mock()
                    self.mock_rgy.reger.creds.get.return_value = mock_cred

                    with patch(
                        "sentinel.core.credentialing.filing.export_credential",
                        new_callable=AsyncMock,
                    ) as mock_export:
                        await loader._save_credential("ESaid123")

                        # Verify export called
                        mock_export.assert_called_once_with(
                            rgy=self.mock_rgy,
                            credential_said="ESaid123",
                            export_dir=self.export_dir,
                        )

    async def test_save_credential_not_found(self):
        """Test save when credential not found"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Credential does not exist
                    self.mock_rgy.reger.creds.get.return_value = None

                    with patch(
                        "sentinel.core.credentialing.filing.export_credential",
                        new_callable=AsyncMock,
                    ) as mock_export:
                        await loader._save_credential("ESaid123")

                        # Verify export not called
                        mock_export.assert_not_called()

    async def test_save_credential_exception_handling(self):
        """Test save handles exceptions gracefully"""
        with patch("sentinel.core.credentialing.verifying.Verifier"):
            with patch("sentinel.core.credentialing.parsing.Parser"):
                with patch("sentinel.core.credentialing.Authenticater"):
                    loader = CredentialLoader(
                        hby=self.mock_hby,
                        hab=self.mock_hab,
                        rgy=self.mock_rgy,
                        export_dir=self.export_dir,
                        registrar_url=self.registrar_url,
                    )

                    # Credential exists
                    mock_cred = Mock()
                    self.mock_rgy.reger.creds.get.return_value = mock_cred

                    with patch(
                        "sentinel.core.credentialing.filing.export_credential",
                        new_callable=AsyncMock,
                    ) as mock_export:
                        mock_export.side_effect = Exception("Export failed")

                        # Should not raise exception
                        await loader._save_credential("ESaid123")

                        # Verify export was attempted
                        mock_export.assert_called_once()


if __name__ == "__main__":
    unittest.main()
