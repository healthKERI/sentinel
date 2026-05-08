# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.core.remoting module
"""

import json
import unittest
from unittest.mock import Mock, patch, AsyncMock

from sentinel.core.remoting import sync_watched_identifier


class TestSyncWatchedIdentifier(unittest.IsolatedAsyncioTestCase):
    """Test cases for sync_watched_identifier function"""

    def setUp(self):
        """Set up test fixtures"""
        self.aid = "ETestAIDPrefix123"
        self.mock_hby = Mock()
        self.mock_hby.psr = Mock()
        self.mock_hby.kvy = Mock()
        self.mock_hby.rvy = Mock()
        self.mock_essr = Mock()

    def _create_multipart_response(self, status_code, doc_data=None, cesr_data=None):
        """Helper to create a mock multipart response"""
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.text = "mock response text"

        # Create mock parts
        parts = []

        if doc_data is not None:
            doc_part = Mock()
            doc_part.headers = {b"content-disposition": b'form-data; name="doc"'}
            doc_part.content = json.dumps(doc_data).encode("utf-8")
            parts.append(doc_part)

        if cesr_data is not None:
            cesr_part = Mock()
            cesr_part.headers = {b"content-disposition": b'form-data; name="cesr"'}
            cesr_part.content = cesr_data
            parts.append(cesr_part)

        # Create mock decoder
        mock_decoder = Mock()
        mock_decoder.parts = parts

        return mock_response, mock_decoder

    async def test_sync_watched_identifier_success_200(self):
        """Test successful sync with status 200"""
        # Setup test data
        doc_data = {"aid": self.aid, "name": "TestIdentifier", "state": {"sn": "5"}}
        cesr_data = b"test-cesr-stream-data"

        mock_response, mock_decoder = self._create_multipart_response(
            200, doc_data, cesr_data
        )

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify API request
        self.mock_essr.request.assert_called_once_with(
            path=f"/watched/{self.aid}", method="GET", timeout=30
        )

        # Verify multipart decoder
        mock_decoder_class.from_response.assert_called_once_with(mock_response)

        # Verify KERI processing
        self.mock_hby.psr.parse.assert_called_once_with(cesr_data)
        self.mock_hby.kvy.processEscrows.assert_called_once()
        self.mock_hby.rvy.processEscrowReply.assert_called_once()

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], doc_data)
        self.assertNotIn("error", result)

    async def test_sync_watched_identifier_success_202(self):
        """Test successful sync with status 202 (accepted)"""
        # Setup test data
        doc_data = {"aid": self.aid, "name": "TestIdentifier"}
        cesr_data = b"test-cesr-stream-data"

        mock_response, mock_decoder = self._create_multipart_response(
            202, doc_data, cesr_data
        )

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], doc_data)

    async def test_sync_watched_identifier_missing_doc_part(self):
        """Test failure when doc part is missing from response"""
        # Setup test data - only cesr, no doc
        cesr_data = b"test-cesr-stream-data"

        mock_response, mock_decoder = self._create_multipart_response(
            200, doc_data=None, cesr_data=cesr_data
        )

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify result - should fail
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid response from connection service")

        # Verify KERI processing was NOT called
        self.mock_hby.psr.parse.assert_not_called()
        self.mock_hby.kvy.processEscrows.assert_not_called()
        self.mock_hby.rvy.processEscrowReply.assert_not_called()

    async def test_sync_watched_identifier_missing_cesr_part(self):
        """Test failure when cesr part is missing from response"""
        # Setup test data - only doc, no cesr
        doc_data = {"aid": self.aid, "name": "TestIdentifier"}

        mock_response, mock_decoder = self._create_multipart_response(
            200, doc_data=doc_data, cesr_data=None
        )

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify result - should fail
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid response from connection service")

        # Verify KERI processing was NOT called
        self.mock_hby.psr.parse.assert_not_called()
        self.mock_hby.kvy.processEscrows.assert_not_called()
        self.mock_hby.rvy.processEscrowReply.assert_not_called()

    async def test_sync_watched_identifier_empty_parts(self):
        """Test failure when response has no parts"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"

        # Create mock decoder with empty parts
        mock_decoder = Mock()
        mock_decoder.parts = []

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify result - should fail
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid response from connection service")

    async def test_sync_watched_identifier_status_400(self):
        """Test failure with status 400 (bad request)"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"description": "Bad request error"}

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call the function
        result = await sync_watched_identifier(
            hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
        )

        # Verify result - should fail
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Bad request error")

        # Verify KERI processing was NOT called
        self.mock_hby.psr.parse.assert_not_called()

    async def test_sync_watched_identifier_status_404(self):
        """Test failure with status 404 (not found)"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"description": "Identifier not found"}

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call the function
        result = await sync_watched_identifier(
            hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
        )

        # Verify result - should fail
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Identifier not found")

    async def test_sync_watched_identifier_status_500(self):
        """Test failure with status 500 (server error)"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"description": "Internal server error"}

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call the function
        result = await sync_watched_identifier(
            hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
        )

        # Verify result - should fail
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Internal server error")

    async def test_sync_watched_identifier_response_no_json(self):
        """Test failure when error response has no JSON"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("No JSON")

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Call the function
        result = await sync_watched_identifier(
            hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
        )

        # Verify result - should fail with status code in error
        self.assertFalse(result["success"])
        self.assertIn("Status 500", result["error"])

    async def test_sync_watched_identifier_no_response(self):
        """Test failure when API returns None response"""
        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=None)

        # Call the function
        result = await sync_watched_identifier(
            hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
        )

        # Verify result - should fail
        self.assertFalse(result["success"])
        self.assertIn("Status N/A", result["error"])

        # Verify KERI processing was NOT called
        self.mock_hby.psr.parse.assert_not_called()

    async def test_sync_watched_identifier_exception_during_request(self):
        """Test exception handling during API request"""
        # Configure mocks to raise exception
        self.mock_essr.request = AsyncMock(side_effect=Exception("Connection timeout"))

        # Call the function
        result = await sync_watched_identifier(
            hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
        )

        # Verify result - should fail with exception message
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Connection timeout")

        # Verify KERI processing was NOT called
        self.mock_hby.psr.parse.assert_not_called()

    async def test_sync_watched_identifier_exception_during_parsing(self):
        """Test exception handling during response parsing"""
        # Setup test data
        doc_data = {"aid": self.aid, "name": "TestIdentifier"}
        cesr_data = b"test-cesr-stream-data"

        mock_response, mock_decoder = self._create_multipart_response(
            200, doc_data, cesr_data
        )

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Make parsing raise exception
        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.side_effect = Exception("Parsing error")

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify result - should fail with exception message
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Parsing error")

        # Verify KERI processing was NOT called
        self.mock_hby.psr.parse.assert_not_called()

    async def test_sync_watched_identifier_exception_during_keri_processing(self):
        """Test exception handling during KERI processing"""
        # Setup test data
        doc_data = {"aid": self.aid, "name": "TestIdentifier"}
        cesr_data = b"test-cesr-stream-data"

        mock_response, mock_decoder = self._create_multipart_response(
            200, doc_data, cesr_data
        )

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Make KERI processing raise exception
        self.mock_hby.psr.parse.side_effect = Exception("KERI parse error")

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify result - should fail with exception message
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "KERI parse error")

        # Verify parse was called but escrow processing was not
        self.mock_hby.psr.parse.assert_called_once()
        self.mock_hby.kvy.processEscrows.assert_not_called()

    async def test_sync_watched_identifier_invalid_json_in_doc(self):
        """Test exception handling when doc part has invalid JSON"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "mock response text"

        # Create doc part with invalid JSON
        doc_part = Mock()
        doc_part.headers = {b"content-disposition": b'form-data; name="doc"'}
        doc_part.content = b"invalid-json-data{"

        cesr_part = Mock()
        cesr_part.headers = {b"content-disposition": b'form-data; name="cesr"'}
        cesr_part.content = b"test-cesr-data"

        mock_decoder = Mock()
        mock_decoder.parts = [doc_part, cesr_part]

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify result - should fail with JSON decode error
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    async def test_sync_watched_identifier_processes_all_keri_steps(self):
        """Test that all three KERI processing steps are called in order"""
        # Setup test data
        doc_data = {"aid": self.aid, "name": "TestIdentifier"}
        cesr_data = b"test-cesr-stream-data"

        mock_response, mock_decoder = self._create_multipart_response(
            200, doc_data, cesr_data
        )

        # Configure mocks with call tracking
        call_order = []
        self.mock_hby.psr.parse = Mock(side_effect=lambda x: call_order.append("parse"))
        self.mock_hby.kvy.processEscrows = Mock(
            side_effect=lambda: call_order.append("kvy")
        )
        self.mock_hby.rvy.processEscrowReply = Mock(
            side_effect=lambda: call_order.append("rvy")
        )

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            result = await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify all steps were called in correct order
        self.assertEqual(call_order, ["parse", "kvy", "rvy"])
        self.assertTrue(result["success"])

    async def test_sync_watched_identifier_correct_timeout_parameter(self):
        """Test that API request uses correct timeout parameter"""
        # Setup test data
        doc_data = {"aid": self.aid, "name": "TestIdentifier"}
        cesr_data = b"test-cesr-stream-data"

        mock_response, mock_decoder = self._create_multipart_response(
            200, doc_data, cesr_data
        )

        # Configure mocks
        self.mock_essr.request = AsyncMock(return_value=mock_response)

        with patch("sentinel.core.remoting.MultipartDecoder") as mock_decoder_class:
            mock_decoder_class.from_response.return_value = mock_decoder

            # Call the function
            await sync_watched_identifier(
                hby=self.mock_hby, essr=self.mock_essr, aid=self.aid
            )

        # Verify timeout parameter
        call_kwargs = self.mock_essr.request.call_args[1]
        self.assertEqual(call_kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
