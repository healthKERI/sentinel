# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.core.authing module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from collections import namedtuple

from keri import kering
from sentinel.core.authing import Authenticater, RequestAuth


class TestAuthenticater(unittest.TestCase):
    """Test cases for Authenticater class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_hab = Mock()
        self.mock_hab.pre = "EHabPrefix123"

        self.mock_agent = Mock()
        self.mock_agent.serder = Mock()
        self.mock_agent.serder.pre = "EAgentPrefix456"

        # Setup verifier
        self.mock_verifier = Mock()
        self.mock_verifier.verify.return_value = True
        self.mock_agent.verfers = [self.mock_verifier]

        self.auth = Authenticater(hab=self.mock_hab, agent=self.mock_agent)

    def test_authenticater_initialization(self):
        """Test Authenticater initialization"""
        auth = Authenticater(hab=self.mock_hab, agent=self.mock_agent)

        self.assertEqual(auth.hab, self.mock_hab)
        self.assertEqual(auth.agent, self.mock_agent)

    def test_authenticater_default_fields(self):
        """Test default signature fields are correct"""
        expected_fields = [
            "@method",
            "@path",
            "Content-Length",
            "Signify-Resource",
            "Signify-Timestamp"
        ]

        self.assertEqual(Authenticater.DefaultFields, expected_fields)

    def test_verify_success(self):
        """Test successful verification of response"""
        # Setup mock response
        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "GET"

        mock_rep = Mock()
        mock_rep.request = mock_request
        mock_rep.headers = {
            "SIGNIFY-RESOURCE": "EAgentPrefix456",
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890',
            "SIGNATURE": "signify=:test_signature:"
        }

        # Mock verifysig to return True
        self.auth.verifysig = Mock(return_value=True)

        # Should not raise exception
        self.auth.verify(mock_rep)

        # Verify verifysig was called
        self.auth.verifysig.assert_called_once_with(
            mock_rep.headers, "GET", "/api/test"
        )

    def test_verify_missing_signify_resource_header(self):
        """Test verification fails when SIGNIFY-RESOURCE header is missing"""
        # Setup mock response without SIGNIFY-RESOURCE
        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"

        mock_rep = Mock()
        mock_rep.request = mock_request
        mock_rep.headers = {
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890',
            "SIGNATURE": "signify=:test_signature:"
        }

        # Should raise AuthNError
        with self.assertRaises(kering.AuthNError) as context:
            self.auth.verify(mock_rep)

        self.assertIn("No valid signature from agent", str(context.exception))

    def test_verify_wrong_resource_prefix(self):
        """Test verification fails when resource prefix doesn't match agent"""
        # Setup mock response with wrong resource
        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "GET"

        mock_rep = Mock()
        mock_rep.request = mock_request
        mock_rep.headers = {
            "SIGNIFY-RESOURCE": "EWrongPrefix789",
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890',
            "SIGNATURE": "signify=:test_signature:"
        }

        # Mock verifysig to return False
        self.auth.verifysig = Mock(return_value=False)

        # Should raise AuthNError
        with self.assertRaises(kering.AuthNError) as context:
            self.auth.verify(mock_rep)

        self.assertIn("No valid signature from agent", str(context.exception))

    def test_verify_invalid_signature(self):
        """Test verification fails when signature is invalid"""
        # Setup mock response
        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "GET"

        mock_rep = Mock()
        mock_rep.request = mock_request
        mock_rep.headers = {
            "SIGNIFY-RESOURCE": "EAgentPrefix456",
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890',
            "SIGNATURE": "signify=:test_signature:"
        }

        # Mock verifysig to return False
        self.auth.verifysig = Mock(return_value=False)

        # Should raise AuthNError
        with self.assertRaises(kering.AuthNError) as context:
            self.auth.verify(mock_rep)

        self.assertIn("No valid signature from agent", str(context.exception))

    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_missing_signature_input(self, mock_desiginput):
        """Test verifysig returns False when SIGNATURE-INPUT header is missing"""
        headers = {
            "SIGNATURE": "signify=:test_signature:"
        }

        result = self.auth.verifysig(headers, "GET", "/api/test")

        self.assertFalse(result)
        mock_desiginput.assert_not_called()

    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_missing_signature(self, mock_desiginput):
        """Test verifysig returns False when SIGNATURE header is missing"""
        headers = {
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890'
        }

        result = self.auth.verifysig(headers, "GET", "/api/test")

        self.assertFalse(result)
        # desiginput should not be called if SIGNATURE is missing
        mock_desiginput.assert_not_called()

    @patch("sentinel.core.authing.ending.designature")
    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_no_signify_input(self, mock_desiginput, mock_designature):
        """Test verifysig returns False when no 'signify' input is found"""
        headers = {
            "SIGNATURE-INPUT": 'other=("@method" "@path");created=1234567890',
            "SIGNATURE": "other=:test_signature:"
        }

        # Mock desiginput to return non-signify input
        MockInput = namedtuple('MockInput', ['name', 'fields'])
        mock_input = MockInput(name='other', fields=['@method', '@path'])
        mock_desiginput.return_value = [mock_input]

        result = self.auth.verifysig(headers, "GET", "/api/test")

        self.assertFalse(result)
        mock_desiginput.assert_called_once()

    @patch("sentinel.core.authing.ending.designature")
    @patch("sentinel.core.authing.ending.normalize")
    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_success_with_method_and_path(
        self, mock_desiginput, mock_normalize, mock_designature
    ):
        """Test successful signature verification with @method and @path fields"""
        headers = {
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890',
            "SIGNATURE": "signify=:test_signature:"
        }

        # Mock desiginput
        MockInput = namedtuple(
            'MockInput',
            ['name', 'fields', 'created', 'expires', 'nonce', 'keyid', 'context', 'alg']
        )
        mock_input = MockInput(
            name='signify',
            fields=['@method', '@path'],
            created=1234567890,
            expires=None,
            nonce=None,
            keyid="EHabPrefix123",
            context=None,
            alg="ed25519"
        )
        mock_desiginput.return_value = [mock_input]

        # Mock designature
        MockCig = namedtuple('MockCig', ['raw'])
        mock_cig = MockCig(raw=b"test_signature_bytes")

        MockSignage = namedtuple('MockSignage', ['markers'])
        mock_signage = MockSignage(markers={'signify': mock_cig})
        mock_designature.return_value = [mock_signage]

        # Mock verifier
        self.mock_verifier.verify.return_value = True

        result = self.auth.verifysig(headers, "GET", "/api/test")

        self.assertTrue(result)
        mock_desiginput.assert_called_once()
        mock_designature.assert_called_once()
        self.mock_verifier.verify.assert_called_once()

    @patch("sentinel.core.authing.ending.designature")
    @patch("sentinel.core.authing.ending.normalize")
    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_success_with_custom_headers(
        self, mock_desiginput, mock_normalize, mock_designature
    ):
        """Test successful verification with custom header fields"""
        headers = {
            "SIGNATURE-INPUT": 'signify=("@method" "@path" "content-length" "signify-resource");created=1234567890',
            "SIGNATURE": "signify=:test_signature:",
            "CONTENT-LENGTH": "1234",
            "SIGNIFY-RESOURCE": "EHabPrefix123"
        }

        # Mock desiginput
        MockInput = namedtuple(
            'MockInput',
            ['name', 'fields', 'created', 'expires', 'nonce', 'keyid', 'context', 'alg']
        )
        mock_input = MockInput(
            name='signify',
            fields=['@method', '@path', 'content-length', 'signify-resource'],
            created=1234567890,
            expires=None,
            nonce=None,
            keyid="EHabPrefix123",
            context=None,
            alg="ed25519"
        )
        mock_desiginput.return_value = [mock_input]

        # Mock normalize
        mock_normalize.side_effect = lambda x: f'"{x}"'

        # Mock designature
        MockCig = namedtuple('MockCig', ['raw'])
        mock_cig = MockCig(raw=b"test_signature_bytes")

        MockSignage = namedtuple('MockSignage', ['markers'])
        mock_signage = MockSignage(markers={'signify': mock_cig})
        mock_designature.return_value = [mock_signage]

        # Mock verifier
        self.mock_verifier.verify.return_value = True

        result = self.auth.verifysig(headers, "GET", "/api/test")

        self.assertTrue(result)
        # normalize should be called for the custom headers
        self.assertEqual(mock_normalize.call_count, 2)

    @patch("sentinel.core.authing.ending.designature")
    @patch("sentinel.core.authing.ending.normalize")
    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_skips_missing_headers(
        self, mock_desiginput, mock_normalize, mock_designature
    ):
        """Test verifysig skips fields when headers are missing"""
        headers = {
            "SIGNATURE-INPUT": 'signify=("@method" "@path" "missing-header");created=1234567890',
            "SIGNATURE": "signify=:test_signature:"
            # missing-header is not present
        }

        # Mock desiginput
        MockInput = namedtuple(
            'MockInput',
            ['name', 'fields', 'created', 'expires', 'nonce', 'keyid', 'context', 'alg']
        )
        mock_input = MockInput(
            name='signify',
            fields=['@method', '@path', 'missing-header'],
            created=1234567890,
            expires=None,
            nonce=None,
            keyid=None,
            context=None,
            alg=None
        )
        mock_desiginput.return_value = [mock_input]

        # Mock designature
        MockCig = namedtuple('MockCig', ['raw'])
        mock_cig = MockCig(raw=b"test_signature_bytes")

        MockSignage = namedtuple('MockSignage', ['markers'])
        mock_signage = MockSignage(markers={'signify': mock_cig})
        mock_designature.return_value = [mock_signage]

        # Mock verifier
        self.mock_verifier.verify.return_value = True

        result = self.auth.verifysig(headers, "GET", "/api/test")

        self.assertTrue(result)
        # normalize should not be called for missing header
        mock_normalize.assert_not_called()

    @patch("sentinel.core.authing.ending.designature")
    @patch("sentinel.core.authing.ending.normalize")
    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_invalid_signature_raises_error(
        self, mock_desiginput, mock_normalize, mock_designature
    ):
        """Test verifysig raises AuthNError when signature verification fails"""
        headers = {
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890',
            "SIGNATURE": "signify=:test_signature:"
        }

        # Mock desiginput
        MockInput = namedtuple(
            'MockInput',
            ['name', 'fields', 'created', 'expires', 'nonce', 'keyid', 'context', 'alg']
        )
        mock_input = MockInput(
            name='signify',
            fields=['@method', '@path'],
            created=1234567890,
            expires=None,
            nonce=None,
            keyid=None,
            context=None,
            alg=None
        )
        mock_desiginput.return_value = [mock_input]

        # Mock designature
        MockCig = namedtuple('MockCig', ['raw'])
        mock_cig = MockCig(raw=b"test_signature_bytes")

        MockSignage = namedtuple('MockSignage', ['markers'])
        mock_signage = MockSignage(markers={'signify': mock_cig})
        mock_designature.return_value = [mock_signage]

        # Mock verifier to return False (invalid signature)
        self.mock_verifier.verify.return_value = False

        # Should raise AuthNError
        with self.assertRaises(kering.AuthNError) as context:
            self.auth.verifysig(headers, "GET", "/api/test")

        self.assertIn("Signature for", str(context.exception))
        self.assertIn("invalid", str(context.exception))

    @patch("sentinel.core.authing.ending.designature")
    @patch("sentinel.core.authing.ending.normalize")
    @patch("sentinel.core.authing.ending.desiginput")
    def test_verifysig_with_all_optional_params(
        self, mock_desiginput, mock_normalize, mock_designature
    ):
        """Test verifysig with all optional parameters (expires, nonce, keyid, context, alg)"""
        headers = {
            "SIGNATURE-INPUT": 'signify=("@method" "@path");created=1234567890;expires=1234567900;nonce="abc123";keyid="EKey123";context="test";alg="ed25519"',
            "SIGNATURE": "signify=:test_signature:"
        }

        # Mock desiginput with all optional fields
        MockInput = namedtuple(
            'MockInput',
            ['name', 'fields', 'created', 'expires', 'nonce', 'keyid', 'context', 'alg']
        )
        mock_input = MockInput(
            name='signify',
            fields=['@method', '@path'],
            created=1234567890,
            expires=1234567900,
            nonce="abc123",
            keyid="EKey123",
            context="test",
            alg="ed25519"
        )
        mock_desiginput.return_value = [mock_input]

        # Mock designature
        MockCig = namedtuple('MockCig', ['raw'])
        mock_cig = MockCig(raw=b"test_signature_bytes")

        MockSignage = namedtuple('MockSignage', ['markers'])
        mock_signage = MockSignage(markers={'signify': mock_cig})
        mock_designature.return_value = [mock_signage]

        # Mock verifier
        self.mock_verifier.verify.return_value = True

        result = self.auth.verifysig(headers, "GET", "/api/test")

        self.assertTrue(result)
        self.mock_verifier.verify.assert_called_once()

    @patch("sentinel.core.authing.ending.signature")
    @patch("sentinel.core.authing.ending.siginput")
    def test_sign_with_default_fields(self, mock_siginput, mock_signature):
        """Test sign method with default fields"""
        headers = {}

        # Mock siginput return values
        mock_qsig = Mock()
        mock_header = {"Signature-Input": 'signify=("@method" "@path");created=1234567890'}
        mock_siginput.return_value = (mock_header, mock_qsig)

        # Mock signature return values
        mock_sig_header = {"Signature": "signify=:test_signature:"}
        mock_signature.return_value = mock_sig_header

        result = self.auth.sign(headers, "POST", "/api/test")

        # Verify siginput was called with default fields
        mock_siginput.assert_called_once_with(
            "signify",
            "POST",
            "/api/test",
            headers,
            fields=Authenticater.DefaultFields,
            hab=self.mock_hab,
            alg="ed25519",
            keyid=self.mock_hab.pre
        )

        # Verify signature was called
        mock_signature.assert_called_once()

        # Verify headers were updated
        self.assertIn("Signature-Input", result)
        self.assertIn("Signature", result)

    @patch("sentinel.core.authing.ending.signature")
    @patch("sentinel.core.authing.ending.siginput")
    def test_sign_with_custom_fields(self, mock_siginput, mock_signature):
        """Test sign method with custom fields"""
        headers = {"Custom-Header": "value"}
        custom_fields = ["@method", "@path", "custom-header"]

        # Mock siginput return values
        mock_qsig = Mock()
        mock_header = {"Signature-Input": 'signify=("@method" "@path" "custom-header");created=1234567890'}
        mock_siginput.return_value = (mock_header, mock_qsig)

        # Mock signature return values
        mock_sig_header = {"Signature": "signify=:test_signature:"}
        mock_signature.return_value = mock_sig_header

        result = self.auth.sign(headers, "GET", "/api/custom", fields=custom_fields)

        # Verify siginput was called with custom fields
        mock_siginput.assert_called_once_with(
            "signify",
            "GET",
            "/api/custom",
            headers,
            fields=custom_fields,
            hab=self.mock_hab,
            alg="ed25519",
            keyid=self.mock_hab.pre
        )

        # Verify headers contain original and new headers
        self.assertIn("Custom-Header", result)
        self.assertIn("Signature-Input", result)
        self.assertIn("Signature", result)

    @patch("sentinel.core.authing.ending.signature")
    @patch("sentinel.core.authing.ending.siginput")
    def test_sign_modifies_headers_in_place(self, mock_siginput, mock_signature):
        """Test that sign modifies the headers dict in place"""
        headers = {"Existing-Header": "value"}

        # Mock siginput return values
        mock_qsig = Mock()
        mock_header = {"Signature-Input": "test_input"}
        mock_siginput.return_value = (mock_header, mock_qsig)

        # Mock signature return values
        mock_sig_header = {"Signature": "test_signature"}
        mock_signature.return_value = mock_sig_header

        result = self.auth.sign(headers, "POST", "/api/test")

        # Verify result is the same dict object
        self.assertIs(result, headers)

        # Verify all headers are present
        self.assertEqual(headers["Existing-Header"], "value")
        self.assertEqual(headers["Signature-Input"], "test_input")
        self.assertEqual(headers["Signature"], "test_signature")


class TestRequestAuth(unittest.TestCase):
    """Test cases for RequestAuth class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_authn = Mock()
        self.mock_authn.hab = Mock()
        self.mock_authn.hab.pre = "EHabPrefix123"

        self.request_auth = RequestAuth(authn=self.mock_authn)

    def test_request_auth_initialization(self):
        """Test RequestAuth initialization"""
        auth = RequestAuth(authn=self.mock_authn)

        self.assertEqual(auth.authn, self.mock_authn)

    @patch("sentinel.core.authing.helping.nowIso8601")
    def test_auth_flow_with_path(self, mock_now):
        """Test auth_flow with a normal path"""
        # Setup
        mock_now.return_value = "2024-01-01T12:00:00Z"

        mock_request = Mock()
        mock_request.url = "http://example.com/api/test?param=value"
        mock_request.method = "GET"
        mock_request.content = b"test content"
        mock_request.headers = {}

        signed_headers = {
            "Signify-Resource": "EHabPrefix123",
            "Signify-Timestamp": "2024-01-01T12:00:00Z",
            "Content-Length": "12",
            "Signature-Input": "test_input",
            "Signature": "test_signature"
        }
        self.mock_authn.sign.return_value = signed_headers

        # Execute
        gen = self.request_auth.auth_flow(mock_request)
        result = next(gen)

        # Verify
        self.assertEqual(result, mock_request)
        self.mock_authn.sign.assert_called_once()

        # Check that headers were set correctly
        call_args = self.mock_authn.sign.call_args
        headers_arg = call_args[0][0]
        method_arg = call_args[0][1]
        path_arg = call_args[0][2]

        self.assertEqual(headers_arg["Signify-Resource"], "EHabPrefix123")
        self.assertEqual(headers_arg["Signify-Timestamp"], "2024-01-01T12:00:00Z")
        self.assertEqual(headers_arg["Content-Length"], 12)
        self.assertEqual(method_arg, "GET")
        self.assertEqual(path_arg, "/api/test")

    @patch("sentinel.core.authing.helping.nowIso8601")
    def test_auth_flow_with_root_path(self, mock_now):
        """Test auth_flow with root path"""
        # Setup
        mock_now.return_value = "2024-01-01T12:00:00Z"

        mock_request = Mock()
        mock_request.url = "http://example.com"
        mock_request.method = "POST"
        mock_request.content = b""
        mock_request.headers = {}

        signed_headers = {
            "Signify-Resource": "EHabPrefix123",
            "Signify-Timestamp": "2024-01-01T12:00:00Z",
            "Signature-Input": "test_input",
            "Signature": "test_signature"
        }
        self.mock_authn.sign.return_value = signed_headers

        # Execute
        gen = self.request_auth.auth_flow(mock_request)
        result = next(gen)

        # Verify path defaults to "/"
        call_args = self.mock_authn.sign.call_args
        path_arg = call_args[0][2]
        self.assertEqual(path_arg, "/")

    @patch("sentinel.core.authing.helping.nowIso8601")
    def test_auth_flow_without_content(self, mock_now):
        """Test auth_flow when request has no content"""
        # Setup
        mock_now.return_value = "2024-01-01T12:00:00Z"

        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "GET"
        mock_request.content = None
        mock_request.headers = {}

        signed_headers = {
            "Signify-Resource": "EHabPrefix123",
            "Signify-Timestamp": "2024-01-01T12:00:00Z",
            "Signature-Input": "test_input",
            "Signature": "test_signature"
        }
        self.mock_authn.sign.return_value = signed_headers

        # Execute
        gen = self.request_auth.auth_flow(mock_request)
        result = next(gen)

        # Verify Content-Length was not added
        call_args = self.mock_authn.sign.call_args
        headers_arg = call_args[0][0]
        self.assertNotIn("Content-Length", headers_arg)

    @patch("sentinel.core.authing.helping.nowIso8601")
    def test_auth_flow_with_existing_content_length(self, mock_now):
        """Test auth_flow when Content-Length already exists"""
        # Setup
        mock_now.return_value = "2024-01-01T12:00:00Z"

        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "POST"
        mock_request.content = b"test content"
        mock_request.headers = {"Content-Length": "999"}

        signed_headers = {
            "Signify-Resource": "EHabPrefix123",
            "Signify-Timestamp": "2024-01-01T12:00:00Z",
            "Content-Length": "999",
            "Signature-Input": "test_input",
            "Signature": "test_signature"
        }
        self.mock_authn.sign.return_value = signed_headers

        # Execute
        gen = self.request_auth.auth_flow(mock_request)
        result = next(gen)

        # Verify Content-Length was not overwritten
        call_args = self.mock_authn.sign.call_args
        headers_arg = call_args[0][0]
        self.assertEqual(headers_arg["Content-Length"], "999")

    @patch("sentinel.core.authing.helping.nowIso8601")
    def test_auth_flow_empty_content(self, mock_now):
        """Test auth_flow with empty content (empty bytes)"""
        # Setup
        mock_now.return_value = "2024-01-01T12:00:00Z"

        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "POST"
        mock_request.content = b""
        mock_request.headers = {}

        signed_headers = {
            "Signify-Resource": "EHabPrefix123",
            "Signify-Timestamp": "2024-01-01T12:00:00Z",
            "Signature-Input": "test_input",
            "Signature": "test_signature"
        }
        self.mock_authn.sign.return_value = signed_headers

        # Execute
        gen = self.request_auth.auth_flow(mock_request)
        result = next(gen)

        # Verify Content-Length was not added (empty content is falsy)
        call_args = self.mock_authn.sign.call_args
        headers_arg = call_args[0][0]
        self.assertNotIn("Content-Length", headers_arg)

    @patch("sentinel.core.authing.helping.nowIso8601")
    def test_auth_flow_updates_request_headers(self, mock_now):
        """Test that auth_flow updates the request headers with signed headers"""
        # Setup
        mock_now.return_value = "2024-01-01T12:00:00Z"

        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "GET"
        mock_request.content = None
        mock_request.headers = {"Existing-Header": "value"}

        signed_headers = {
            "Signify-Resource": "EHabPrefix123",
            "Signify-Timestamp": "2024-01-01T12:00:00Z",
            "Signature-Input": "test_input",
            "Signature": "test_signature",
            "Existing-Header": "value"
        }
        self.mock_authn.sign.return_value = signed_headers

        # Execute
        gen = self.request_auth.auth_flow(mock_request)
        result = next(gen)

        # Verify request headers were updated
        self.assertEqual(result.headers, signed_headers)

    @patch("sentinel.core.authing.helping.nowIso8601")
    def test_auth_flow_generator_completes(self, mock_now):
        """Test that auth_flow generator completes after yielding request"""
        # Setup
        mock_now.return_value = "2024-01-01T12:00:00Z"

        mock_request = Mock()
        mock_request.url = "http://example.com/api/test"
        mock_request.method = "GET"
        mock_request.content = None
        mock_request.headers = {}

        signed_headers = {"Signify-Resource": "EHabPrefix123"}
        self.mock_authn.sign.return_value = signed_headers

        # Execute
        gen = self.request_auth.auth_flow(mock_request)
        result = next(gen)

        # Verify generator completes (raises StopIteration)
        with self.assertRaises(StopIteration):
            next(gen)


if __name__ == "__main__":
    unittest.main()
