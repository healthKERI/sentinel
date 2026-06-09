# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.core.watching module
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, AsyncMock

from sentinel.core.watching import (
    fetch_account_watched,
    delete_account_watcher,
    add_watched_identifier,
    WatchedAdjudicationPoller,
    ObvsSocketListener,
)


class TestFetchAccountWatched(unittest.IsolatedAsyncioTestCase):
    """Test cases for fetch_account_watched function"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_essr = Mock()

    async def test_fetch_account_watched_success(self):
        """Test successful fetch with default parameters"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "watchers": [{"aid": "ETest123", "name": "Test"}],
            "total": 1,
        }

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call function
        result = await fetch_account_watched(essr=self.mock_essr)

        # Verify API call
        self.mock_essr.request.assert_called_once_with(
            path="/watched?page=0&page_size=10", method="GET"
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["watchers"]), 1)

    async def test_fetch_account_watched_with_pagination(self):
        """Test fetch with custom page and page_size"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"watchers": [], "total": 0}

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call with custom pagination
        result = await fetch_account_watched(essr=self.mock_essr, page=2, page_size=25)

        # Verify API call includes pagination
        self.mock_essr.request.assert_called_once_with(
            path="/watched?page=2&page_size=25", method="GET"
        )

        self.assertTrue(result["success"])

    async def test_fetch_account_watched_with_filter(self):
        """Test fetch with filter term"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"watchers": [], "total": 0}

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call with filter
        result = await fetch_account_watched(
            essr=self.mock_essr, filter_term="test filter"
        )

        # Verify API call includes encoded filter
        call_args = self.mock_essr.request.call_args[1]
        self.assertIn("filter=test%20filter", call_args["path"])
        self.assertTrue(result["success"])

    async def test_fetch_account_watched_with_order(self):
        """Test fetch with order parameters"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"watchers": [], "total": 0}

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call with order
        result = await fetch_account_watched(
            essr=self.mock_essr, order=["+name", "-eid"]
        )

        # Verify API call includes order params
        call_args = self.mock_essr.request.call_args[1]
        path = call_args["path"]
        self.assertIn("order=%2Bname", path)
        self.assertIn("order=-eid", path)
        self.assertTrue(result["success"])

    async def test_fetch_account_watched_api_error(self):
        """Test fetch with API error response"""
        mock_response = Mock()
        mock_response.status_code = 500

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call function
        result = await fetch_account_watched(essr=self.mock_essr)

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("API error", result["error"])
        self.assertIn("500", result["error"])

    async def test_fetch_account_watched_no_response(self):
        """Test fetch with no response"""
        self.mock_essr.request = AsyncMock(return_value=None)

        # Call function
        result = await fetch_account_watched(essr=self.mock_essr)

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("No response", result["error"])

    async def test_fetch_account_watched_exception(self):
        """Test fetch with exception during request"""
        self.mock_essr.request = AsyncMock(side_effect=Exception("Connection error"))

        # Call function
        result = await fetch_account_watched(essr=self.mock_essr)

        # Verify error result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Connection error")


class TestDeleteAccountWatcher(unittest.IsolatedAsyncioTestCase):
    """Test cases for delete_account_watcher function"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_essr = Mock()
        self.eid = "ETestWatcher123"

    async def test_delete_account_watcher_success(self):
        """Test successful watcher deletion"""
        mock_response = Mock()
        mock_response.status_code = 204

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call function
        result = await delete_account_watcher(essr=self.mock_essr, eid=self.eid)

        # Verify API call
        self.mock_essr.request.assert_called_once_with(
            path=f"/watched/{self.eid}", method="DELETE"
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertNotIn("error", result)

    async def test_delete_account_watcher_error_with_description(self):
        """Test deletion with error response containing description"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"description": "Watcher not found"}

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call function
        result = await delete_account_watcher(essr=self.mock_essr, eid=self.eid)

        # Verify error result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Watcher not found")

    async def test_delete_account_watcher_error_without_json(self):
        """Test deletion with error response without JSON"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("No JSON")

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call function
        result = await delete_account_watcher(essr=self.mock_essr, eid=self.eid)

        # Verify error result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Status 500")

    async def test_delete_account_watcher_no_response(self):
        """Test deletion with no response"""
        self.mock_essr.request = AsyncMock(return_value=None)

        # Call function
        result = await delete_account_watcher(essr=self.mock_essr, eid=self.eid)

        # Verify error result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Unknown error")

    async def test_delete_account_watcher_exception(self):
        """Test deletion with exception"""
        self.mock_essr.request = AsyncMock(side_effect=Exception("Network timeout"))

        # Call function
        result = await delete_account_watcher(essr=self.mock_essr, eid=self.eid)

        # Verify error result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Network timeout")


class TestAddWatchedIdentifier(unittest.IsolatedAsyncioTestCase):
    """Test cases for add_watched_identifier function"""

    def setUp(self):
        """Set up test fixtures"""
        self.watched_aid = "EWatchedAID123"
        self.alias = "TestAlias"
        self.mock_hby = Mock()
        self.mock_essr = Mock()

    async def test_add_watched_identifier_success_https(self):
        """Test successful add with HTTPS witness URL"""
        # Setup mocks
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]
        mock_serder = Mock()
        mock_serder.pre = self.watched_aid
        mock_kever.serder = mock_serder

        self.mock_hby.kevers = {self.watched_aid: mock_kever}

        # Setup witness location with HTTPS
        mock_loc = Mock()
        mock_loc.url = "https://witness.example.com"
        self.mock_hby.db.locs.getItemIter = Mock(
            return_value=[(("EWitness123", "https"), mock_loc)]
        )

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.text = "Created"
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.watching.random.choice", return_value="EWitness123"):
            with patch("sentinel.core.watching.kering.Schemes") as mock_schemes:
                mock_schemes.https = "https"
                mock_schemes.http = "http"

                # Call function
                result = await add_watched_identifier(
                    hby=self.mock_hby,
                    essr=self.mock_essr,
                    watched_aid=self.watched_aid,
                    alias=self.alias,
                )

        # Verify API call
        self.mock_essr.request.assert_called_once()
        call_kwargs = self.mock_essr.request.call_args[1]
        self.assertEqual(call_kwargs["path"], "/watched")
        self.assertEqual(call_kwargs["method"], "POST")
        self.assertEqual(call_kwargs["json"]["name"], self.alias)
        self.assertEqual(call_kwargs["json"]["aid"], self.watched_aid)
        self.assertIn("oobi", call_kwargs["json"])

        # Verify result
        self.assertTrue(result["success"])

    async def test_add_watched_identifier_success_http_fallback(self):
        """Test successful add with HTTP witness URL fallback"""
        # Setup mocks
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]
        mock_serder = Mock()
        mock_serder.pre = self.watched_aid
        mock_kever.serder = mock_serder

        self.mock_hby.kevers = {self.watched_aid: mock_kever}

        # Setup witness location with only HTTP
        mock_loc = Mock()
        mock_loc.url = "http://witness.example.com"
        self.mock_hby.db.locs.getItemIter = Mock(
            return_value=[(("EWitness123", "http"), mock_loc)]
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.watching.random.choice", return_value="EWitness123"):
            with patch("sentinel.core.watching.kering.Schemes") as mock_schemes:
                mock_schemes.https = "https"
                mock_schemes.http = "http"

                # Call function
                result = await add_watched_identifier(
                    hby=self.mock_hby,
                    essr=self.mock_essr,
                    watched_aid=self.watched_aid,
                    alias=self.alias,
                )

        # Verify result
        self.assertTrue(result["success"])

    async def test_add_watched_identifier_not_in_kevers(self):
        """Test add when identifier not found in kevers"""
        self.mock_hby.kevers = {}

        # Call function
        result = await add_watched_identifier(
            hby=self.mock_hby,
            essr=self.mock_essr,
            watched_aid=self.watched_aid,
            alias=self.alias,
        )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("not found in KERI database", result["error"])

    async def test_add_watched_identifier_no_witnesses(self):
        """Test add when identifier has no witnesses"""
        mock_kever = Mock()
        mock_kever.wits = []

        self.mock_hby.kevers = {self.watched_aid: mock_kever}

        # Call function
        result = await add_watched_identifier(
            hby=self.mock_hby,
            essr=self.mock_essr,
            watched_aid=self.watched_aid,
            alias=self.alias,
        )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("does not have witnesses", result["error"])

    async def test_add_watched_identifier_no_witness_urls(self):
        """Test add when witness has no HTTP endpoint"""
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]

        self.mock_hby.kevers = {self.watched_aid: mock_kever}
        self.mock_hby.db.locs.getItemIter = Mock(return_value=[])

        with patch("sentinel.core.watching.random.choice", return_value="EWitness123"):
            # Call function
            result = await add_watched_identifier(
                hby=self.mock_hby,
                essr=self.mock_essr,
                watched_aid=self.watched_aid,
                alias=self.alias,
            )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("no http endpoint", result["error"])

    async def test_add_watched_identifier_api_error(self):
        """Test add with API error response"""
        # Setup mocks
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]
        mock_serder = Mock()
        mock_serder.pre = self.watched_aid
        mock_kever.serder = mock_serder

        self.mock_hby.kevers = {self.watched_aid: mock_kever}

        mock_loc = Mock()
        mock_loc.url = "https://witness.example.com"
        self.mock_hby.db.locs.getItemIter = Mock(
            return_value=[(("EWitness123", "https"), mock_loc)]
        )

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {"description": "Invalid data"}
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.watching.random.choice", return_value="EWitness123"):
            with patch("sentinel.core.watching.kering.Schemes") as mock_schemes:
                mock_schemes.https = "https"
                mock_schemes.http = "http"

                # Call function
                result = await add_watched_identifier(
                    hby=self.mock_hby,
                    essr=self.mock_essr,
                    watched_aid=self.watched_aid,
                    alias=self.alias,
                )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid data")

    async def test_add_watched_identifier_oobi_resolution_success(self):
        """Test successful OOBI resolution when AID not in kevers"""
        # Setup mocks - watched_aid NOT in kevers initially
        self.mock_hby.kevers = {}

        # Setup kever that will be added after OOBI resolution
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]
        mock_serder = Mock()
        mock_serder.pre = self.watched_aid
        mock_kever.serder = mock_serder

        # Setup witness location
        mock_loc = Mock()
        mock_loc.url = "https://witness.example.com"
        self.mock_hby.db.locs.getItemIter = Mock(
            return_value=[(("EWitness123", "https"), mock_loc)]
        )

        # Setup psr and kvy for parsing
        self.mock_hby.psr = Mock()
        self.mock_hby.psr.parse = Mock()
        self.mock_hby.kvy = Mock()
        self.mock_hby.kvy.processEscrows = Mock()
        self.mock_hby.rvy = Mock()
        self.mock_hby.rvy.processEscrowReply = Mock()

        # Mock the OOBI HTTP response
        mock_oobi_response = Mock()
        mock_oobi_response.status_code = 200
        mock_oobi_response.content = b"mock_oobi_data"

        # Mock the final API response
        mock_api_response = Mock()
        mock_api_response.status_code = 201
        mock_api_response.text = "Created"
        self.mock_essr.request = AsyncMock(return_value=mock_api_response)

        with patch("sentinel.core.watching.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_oobi_response)
            mock_client_class.return_value = mock_client

            with patch("sentinel.core.watching.filing.export_kel", new_callable=AsyncMock) as mock_export:
                mock_export.return_value = True

                # After parse is called, add kever to mock_hby.kevers
                def add_kever_after_parse(data):
                    self.mock_hby.kevers[self.watched_aid] = mock_kever

                self.mock_hby.psr.parse.side_effect = add_kever_after_parse

                with patch("sentinel.core.watching.random.choice", return_value="EWitness123"):
                    with patch("sentinel.core.watching.kering.Schemes") as mock_schemes:
                        mock_schemes.https = "https"
                        mock_schemes.http = "http"

                        # Call function with registrar_url and export_dir
                        result = await add_watched_identifier(
                            hby=self.mock_hby,
                            essr=self.mock_essr,
                            watched_aid=self.watched_aid,
                            alias=self.alias,
                            registrar_url="https://registrar.example.com",
                            export_dir="/tmp/test",
                        )

                # Verify OOBI fetch was called
                mock_client.get.assert_called_once_with(
                    f"https://registrar.example.com/oobi/{self.watched_aid}"
                )

                # Verify parse was called
                self.mock_hby.psr.parse.assert_called_once_with(b"mock_oobi_data")

                # Verify export was called
                mock_export.assert_called_once_with(
                    hby=self.mock_hby,
                    aid=self.watched_aid,
                    export_dir="/tmp/test"
                )

        # Verify result
        self.assertTrue(result["success"])

    async def test_add_watched_identifier_oobi_resolution_404(self):
        """Test OOBI resolution with 404 from registrar"""
        # Setup mocks - watched_aid NOT in kevers
        self.mock_hby.kevers = {}

        # Mock the OOBI HTTP response - 404
        mock_oobi_response = Mock()
        mock_oobi_response.status_code = 404

        with patch("sentinel.core.watching.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_oobi_response)
            mock_client_class.return_value = mock_client

            # Call function with registrar_url
            result = await add_watched_identifier(
                hby=self.mock_hby,
                essr=self.mock_essr,
                watched_aid=self.watched_aid,
                alias=self.alias,
                registrar_url="https://registrar.example.com",
            )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("not found in KERI database or registrar", result["error"])

    async def test_add_watched_identifier_oobi_resolution_non_200(self):
        """Test OOBI resolution with non-200 status from registrar"""
        # Setup mocks - watched_aid NOT in kevers
        self.mock_hby.kevers = {}

        # Mock the OOBI HTTP response - 500
        mock_oobi_response = Mock()
        mock_oobi_response.status_code = 500

        with patch("sentinel.core.watching.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_oobi_response)
            mock_client_class.return_value = mock_client

            # Call function with registrar_url
            result = await add_watched_identifier(
                hby=self.mock_hby,
                essr=self.mock_essr,
                watched_aid=self.watched_aid,
                alias=self.alias,
                registrar_url="https://registrar.example.com",
            )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("Failed to fetch OOBI from registrar", result["error"])
        self.assertIn("500", result["error"])

    async def test_add_watched_identifier_oobi_resolution_http_error(self):
        """Test OOBI resolution with HTTP error"""
        # Setup mocks - watched_aid NOT in kevers
        self.mock_hby.kevers = {}

        with patch("sentinel.core.watching.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            # Use httpx.HTTPError for proper exception handling
            import httpx
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection timeout"))
            mock_client_class.return_value = mock_client

            # Call function with registrar_url
            result = await add_watched_identifier(
                hby=self.mock_hby,
                essr=self.mock_essr,
                watched_aid=self.watched_aid,
                alias=self.alias,
                registrar_url="https://registrar.example.com",
            )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("Network error fetching OOBI from registrar", result["error"])

    async def test_add_watched_identifier_no_registrar_url(self):
        """Test fallback when no registrar_url provided"""
        # Setup mocks - watched_aid NOT in kevers
        self.mock_hby.kevers = {}

        # Call function without registrar_url
        result = await add_watched_identifier(
            hby=self.mock_hby,
            essr=self.mock_essr,
            watched_aid=self.watched_aid,
            alias=self.alias,
        )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("not found in KERI database", result["error"])

    async def test_add_watched_identifier_oobi_resolution_kel_not_loaded(self):
        """Test KEL not loaded after OOBI resolution"""
        # Setup mocks - watched_aid NOT in kevers initially
        self.mock_hby.kevers = {}

        # Setup psr and kvy for parsing
        self.mock_hby.psr = Mock()
        self.mock_hby.psr.parse = Mock()
        self.mock_hby.kvy = Mock()
        self.mock_hby.kvy.processEscrows = Mock()
        self.mock_hby.rvy = Mock()
        self.mock_hby.rvy.processEscrowReply = Mock()

        # Mock the OOBI HTTP response
        mock_oobi_response = Mock()
        mock_oobi_response.status_code = 200
        mock_oobi_response.content = b"mock_oobi_data"

        with patch("sentinel.core.watching.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_oobi_response)
            mock_client_class.return_value = mock_client

            # Call function with registrar_url - kever NOT added after parse
            result = await add_watched_identifier(
                hby=self.mock_hby,
                essr=self.mock_essr,
                watched_aid=self.watched_aid,
                alias=self.alias,
                registrar_url="https://registrar.example.com",
            )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("could not be resolved", result["error"])

    async def test_add_watched_identifier_max_retry(self):
        """Test retry limit prevention"""
        # Setup mocks - watched_aid NOT in kevers
        self.mock_hby.kevers = {}

        # Call function with _retry_count > MAX_RETRY_COUNT
        result = await add_watched_identifier(
            hby=self.mock_hby,
            essr=self.mock_essr,
            watched_aid=self.watched_aid,
            alias=self.alias,
            registrar_url="https://registrar.example.com",
            _retry_count=2,  # Greater than MAX_RETRY_COUNT (1)
        )

        # Verify error result
        self.assertFalse(result["success"])
        self.assertIn("after retry", result["error"])

    async def test_add_watched_identifier_oobi_resolution_export_failure(self):
        """Test export failure handling during OOBI resolution"""
        # Setup mocks - watched_aid NOT in kevers initially
        self.mock_hby.kevers = {}

        # Setup kever that will be added after OOBI resolution
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]
        mock_serder = Mock()
        mock_serder.pre = self.watched_aid
        mock_kever.serder = mock_serder

        # Setup witness location
        mock_loc = Mock()
        mock_loc.url = "https://witness.example.com"
        self.mock_hby.db.locs.getItemIter = Mock(
            return_value=[(("EWitness123", "https"), mock_loc)]
        )

        # Setup psr and kvy for parsing
        self.mock_hby.psr = Mock()
        self.mock_hby.psr.parse = Mock()
        self.mock_hby.kvy = Mock()
        self.mock_hby.kvy.processEscrows = Mock()
        self.mock_hby.rvy = Mock()
        self.mock_hby.rvy.processEscrowReply = Mock()

        # Mock the OOBI HTTP response
        mock_oobi_response = Mock()
        mock_oobi_response.status_code = 200
        mock_oobi_response.content = b"mock_oobi_data"

        # Mock the final API response
        mock_api_response = Mock()
        mock_api_response.status_code = 201
        mock_api_response.text = "Created"
        self.mock_essr.request = AsyncMock(return_value=mock_api_response)

        with patch("sentinel.core.watching.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_oobi_response)
            mock_client_class.return_value = mock_client

            with patch("sentinel.core.watching.filing.export_kel", new_callable=AsyncMock) as mock_export:
                # Export fails
                mock_export.side_effect = Exception("Export error")

                # After parse is called, add kever to mock_hby.kevers
                def add_kever_after_parse(data):
                    self.mock_hby.kevers[self.watched_aid] = mock_kever

                self.mock_hby.psr.parse.side_effect = add_kever_after_parse

                with patch("sentinel.core.watching.random.choice", return_value="EWitness123"):
                    with patch("sentinel.core.watching.kering.Schemes") as mock_schemes:
                        mock_schemes.https = "https"
                        mock_schemes.http = "http"

                        # Call function with registrar_url and export_dir
                        result = await add_watched_identifier(
                            hby=self.mock_hby,
                            essr=self.mock_essr,
                            watched_aid=self.watched_aid,
                            alias=self.alias,
                            registrar_url="https://registrar.example.com",
                            export_dir="/tmp/test",
                        )

        # Verify result - should still succeed despite export failure
        self.assertTrue(result["success"])


class TestWatchedAdjudicationPoller(unittest.IsolatedAsyncioTestCase):
    """Test cases for WatchedAdjudicationPoller class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_hby = Mock()
        self.mock_hby.kevers = {}
        self.mock_rgy = Mock()
        self.mock_essr = Mock()
        self.mock_db = Mock()
        self.mock_db.watched_poll = Mock()

    def test_init(self):
        """Test poller initialization"""
        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=15.0,
            export_dir="/tmp/test",
        )

        self.assertEqual(poller.hby, self.mock_hby)
        self.assertEqual(poller.essr, self.mock_essr)
        self.assertEqual(poller.db, self.mock_db)
        self.assertEqual(poller.poll_interval, 15.0)
        self.assertEqual(poller.export_dir, "/tmp/test")
        self.assertTrue(poller.query_done)
        self.assertIsNone(poller._task)
        self.assertFalse(poller._running)

    def test_init_default_export_dir(self):
        """Test poller initialization with default export_dir"""
        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=15.0,
        )

        self.assertEqual(poller.export_dir, "/usr/local/sentinel")

    async def test_start(self):
        """Test starting the poller"""
        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=0.1,
        )

        task = poller.start()

        # Verify task created
        self.assertIsNotNone(task)
        self.assertIsInstance(task, asyncio.Task)
        self.assertEqual(poller._task, task)

        # Cleanup
        poller.stop()
        try:
            await asyncio.wait_for(task, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    async def test_stop(self):
        """Test stopping the poller"""
        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=0.1,
        )

        task = poller.start()
        poller.stop()

        # Verify state
        self.assertFalse(poller._running)

        # Wait for task to finish
        try:
            await asyncio.wait_for(task, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

        self.assertTrue(task.cancelled() or task.done())

    async def test_run_no_db(self):
        """Test run with no database"""
        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=None,
            poll_interval=0.01,
        )

        # Run briefly and stop
        task = asyncio.create_task(poller.run())
        await asyncio.sleep(0.05)
        poller.stop()

        # Wait for task to finish
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.CancelledError:
            pass

        # Verify no API calls made
        self.mock_essr.request = AsyncMock()
        self.mock_essr.request.assert_not_called()

    async def test_run_no_watched_poll(self):
        """Test run with no watched_poll table"""
        self.mock_db.watched_poll = None

        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=0.01,
        )

        # Run briefly and stop
        task = asyncio.create_task(poller.run())
        await asyncio.sleep(0.05)
        poller.stop()

        # Wait for task to finish
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.CancelledError:
            pass

    async def test_async_poll_adjudications_success(self):
        """Test successful adjudication polling"""
        # Setup mocks
        mock_dater = Mock()
        mock_dater.dts = "2024-01-01T00:00:00+00:00"
        self.mock_db.watched_poll.get.return_value = mock_dater
        self.mock_db.watched_poll.pin = Mock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.json.return_value = {
            "adjudications": [{"watched_aid": "ETest123", "sn": "5"}]
        }

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Setup kever
        mock_kever = Mock()
        mock_kever.pre = "ETest123"
        mock_sner = Mock()
        mock_sner.num = 3
        mock_kever.sner = mock_sner
        self.mock_hby.kevers = {"ETest123": mock_kever}

        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=0.1,
        )

        with patch("sentinel.core.watching.Organizer") as mock_org_class:
            mock_org = Mock()
            mock_org.get.return_value = {"alias": "TestName"}
            mock_org_class.return_value = mock_org

            with patch(
                "sentinel.core.watching.remoting.sync_watched_identifier",
                new_callable=AsyncMock,
            ) as mock_sync:
                with patch("sentinel.core.watching.coring.Dater"):
                    # Call the method
                    await poller._async_poll_adjudications(
                        "/adjudications?date=2024-01-01"
                    )

        # Verify sync was called
        mock_sync.assert_called_once()

        # Verify query_done reset
        self.assertTrue(poller.query_done)

    async def test_async_poll_adjudications_no_response(self):
        """Test polling with no response"""
        self.mock_essr.request = AsyncMock(return_value=None)

        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=0.1,
        )

        await poller._async_poll_adjudications("/adjudications")

        # Verify query_done reset
        self.assertTrue(poller.query_done)

    async def test_async_poll_adjudications_error_status(self):
        """Test polling with error status code"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        poller = WatchedAdjudicationPoller(
            hby=self.mock_hby,
            rgy=self.mock_rgy,
            essr=self.mock_essr,
            db=self.mock_db,
            poll_interval=0.1,
        )

        await poller._async_poll_adjudications("/adjudications")

        # Verify query_done reset
        self.assertTrue(poller.query_done)


class TestObvsSocketListener(unittest.IsolatedAsyncioTestCase):
    """Test cases for ObvsSocketListener class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_hby = Mock()
        self.mock_hby.kvy = Mock()
        self.mock_hby.rvy = Mock()
        self.mock_hby.db = Mock()
        self.mock_hby.db.obvs = Mock()
        self.mock_essr = Mock()
        self.mock_db = Mock()
        self.mock_db.watched_poll = Mock()
        self.socket_path = tempfile.mktemp(suffix=".sock")

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def test_init(self):
        """Test socket listener initialization"""
        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.5,
            )

            self.assertEqual(listener.hby, self.mock_hby)
            self.assertEqual(listener.essr, self.mock_essr)
            self.assertEqual(listener.db, self.mock_db)
            self.assertEqual(listener.socket_path, self.socket_path)
            self.assertEqual(listener.poll_interval, 0.5)
            self.assertIsNone(listener._server)
            self.assertIsNone(listener._task)
            self.assertFalse(listener._running)
            self.assertEqual(len(listener._connection_tasks), 0)

    async def test_start(self):
        """Test starting the socket listener"""
        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            task = listener.start()

            # Verify task created
            self.assertIsNotNone(task)
            self.assertIsInstance(task, asyncio.Task)
            self.assertEqual(listener._task, task)

            # Cleanup
            listener.stop()
            try:
                await asyncio.wait_for(task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

    async def test_stop(self):
        """Test stopping the socket listener"""
        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            task = listener.start()
            listener.stop()

            # Verify state
            self.assertFalse(listener._running)

            # Wait for task to finish
            try:
                await asyncio.wait_for(task, timeout=0.5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

            self.assertTrue(task.cancelled() or task.done())

    async def test_handle_connection(self):
        """Test connection handling"""
        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            mock_reader = Mock()
            mock_writer = Mock()

            # Call handle connection
            await listener._handle_connection(mock_reader, mock_writer)

            # Verify a task was created
            self.assertEqual(len(listener._connection_tasks), 1)

    async def test_process_connection(self):
        """Test connection processing"""
        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            # Setup mocks
            mock_reader = AsyncMock()
            mock_reader.read.side_effect = [b"test data", b""]

            mock_writer = Mock()
            mock_writer.get_extra_info.return_value = "test_peer"
            mock_writer.close = Mock()
            mock_writer.wait_closed = AsyncMock()

            listener.psr = Mock()
            listener.psr.parseOne = Mock()
            listener.hby.db.obvs.trim = Mock()

            with patch.object(
                listener, "_check_and_add_obvs", new_callable=AsyncMock
            ) as mock_check:
                # Call process connection
                await listener._process_connection(mock_reader, mock_writer)

                # Verify check was called
                mock_check.assert_called_once()

            # Verify writer closed
            mock_writer.close.assert_called_once()

    async def test_check_and_add_obvs_no_db(self):
        """Test obvs checking with no database"""
        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=None,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            # Call check method
            await listener._check_and_add_obvs()

            # Should return early without error

    async def test_check_and_add_obvs_no_watched_poll(self):
        """Test obvs checking with no watched_poll table"""
        self.mock_db.watched_poll = None

        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            # Call check method
            await listener._check_and_add_obvs()

            # Should return early without error

    async def test_check_and_add_obvs_success(self):
        """Test successful obvs checking and adding"""
        # Setup mocks
        mock_dater = Mock()
        mock_dater.dts = "2024-01-01T00:00:00+00:00"
        self.mock_db.watched_poll.get.return_value = mock_dater
        self.mock_db.watched_poll.pin = Mock()

        mock_observed = Mock()
        mock_observed.datetime = "2024-01-02T00:00:00+00:00"
        mock_observed.name = "TestObvs"

        self.mock_hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), mock_observed)
        ]

        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            with patch(
                "sentinel.core.watching.add_watched_identifier", new_callable=AsyncMock
            ) as mock_add:
                mock_add.return_value = {"success": True}

                with patch("sentinel.core.watching.coring.Dater"):
                    # Call check method
                    await listener._check_and_add_obvs()

                # Verify add_watched_identifier was called
                mock_add.assert_called_once_with(
                    hby=self.mock_hby,
                    essr=self.mock_essr,
                    watched_aid="oid1",
                    alias="TestObvs",
                    registrar_url=None,
                    export_dir=None,
                )

    async def test_check_and_add_obvs_skip_old_entries(self):
        """Test that old obvs entries are skipped"""
        # Setup mocks
        mock_dater = Mock()
        mock_dater.dts = "2024-01-02T00:00:00+00:00"
        self.mock_db.watched_poll.get.return_value = mock_dater
        self.mock_db.watched_poll.pin = Mock()

        mock_observed = Mock()
        mock_observed.datetime = "2024-01-01T00:00:00+00:00"  # Older than last check
        mock_observed.name = "TestObvs"

        self.mock_hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), mock_observed)
        ]

        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            with patch(
                "sentinel.core.watching.add_watched_identifier", new_callable=AsyncMock
            ) as mock_add:
                with patch("sentinel.core.watching.coring.Dater"):
                    # Call check method
                    await listener._check_and_add_obvs()

                # Verify add_watched_identifier was NOT called
                mock_add.assert_not_called()

    async def test_check_and_add_obvs_skip_no_datetime(self):
        """Test that obvs entries without datetime are skipped"""
        # Setup mocks
        self.mock_db.watched_poll.get.return_value = None
        self.mock_db.watched_poll.pin = Mock()

        mock_observed = Mock()
        mock_observed.datetime = None  # No datetime
        mock_observed.name = "TestObvs"

        self.mock_hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), mock_observed)
        ]

        with patch("sentinel.core.watching.parsing.Parser"):
            listener = ObvsSocketListener(
                hby=self.mock_hby,
                essr=self.mock_essr,
                db=self.mock_db,
                socket_path=self.socket_path,
                poll_interval=0.1,
            )

            with patch(
                "sentinel.core.watching.add_watched_identifier", new_callable=AsyncMock
            ) as mock_add:
                with patch("sentinel.core.watching.coring.Dater"):
                    # Call check method
                    await listener._check_and_add_obvs()

                # Verify add_watched_identifier was NOT called
                mock_add.assert_not_called()


if __name__ == "__main__":
    unittest.main()
