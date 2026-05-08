# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.core.eventing module
"""

import json
import unittest
from unittest.mock import Mock, patch, AsyncMock

from sentinel.core.eventing import sync_server_key_state


class TestSyncServerKeyState(unittest.IsolatedAsyncioTestCase):
    """Test cases for sync_server_key_state function"""

    def setUp(self):
        """Set up test fixtures"""
        self.name = "test_sentinel"
        self.alias = "test_alias"
        self.base = "/tmp/test"
        self.bran = "test_bran"
        self.mock_essr = Mock()

    @patch("sentinel.core.eventing.habbing.Habery")
    async def test_sync_server_key_state_alias_not_found(self, mock_habery_class):
        """Test error when alias is not found"""
        # Setup mocks
        mock_hby = Mock()
        mock_hby.habByName.return_value = None
        mock_habery_class.return_value = mock_hby

        # Call function and expect ValueError
        with self.assertRaises(ValueError) as context:
            await sync_server_key_state(
                name=self.name,
                alias=self.alias,
                base=self.base,
                bran=self.bran,
                essr=self.mock_essr,
            )

        # Verify error message
        self.assertEqual(
            str(context.exception),
            f"Server alias '{self.alias}' not found in Habery '{self.name}'",
        )

        # Verify Habery was initialized
        mock_habery_class.assert_called_once_with(
            name=self.name, base=self.base, bran=self.bran
        )

        # Verify habByName was called
        mock_hby.habByName.assert_called_once_with(self.alias)

    @patch("sentinel.core.eventing.dbing.dgKey")
    @patch("sentinel.core.eventing.habbing.Habery")
    async def test_sync_server_key_state_with_existing_seal_and_wigs(
        self, mock_habery_class, mock_dgkey
    ):
        """Test successful execution when seal and wigs already exist"""
        # Setup mocks
        mock_hab = Mock()
        mock_kever = Mock()
        mock_serder = Mock()
        mock_serder.preb = b"test_preb"
        mock_serder.saidb = b"test_saidb"
        mock_kever.serder = mock_serder
        mock_hab.kever = mock_kever

        mock_db = Mock()
        mock_db.getAes.return_value = b"existing_seal"
        mock_db.getWigs.return_value = [b"existing_wig"]
        mock_hab.db = mock_db

        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_habery_class.return_value = mock_hby

        mock_dgkey.return_value = b"test_dgkey"

        # Call function
        await sync_server_key_state(
            name=self.name,
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            essr=self.mock_essr,
        )

        # Verify Habery was initialized
        mock_habery_class.assert_called_once_with(
            name=self.name, base=self.base, bran=self.bran
        )

        # Verify habByName was called
        mock_hby.habByName.assert_called_once_with(self.alias)

        # Verify dgKey was called at least once
        self.assertGreaterEqual(mock_dgkey.call_count, 1)

        # Verify getAes was called
        mock_db.getAes.assert_called_once()

        # Verify getWigs was called
        mock_db.getWigs.assert_called_once()

        # Verify no API requests were made (seal and wigs exist)
        self.mock_essr.request.assert_not_called()

    @patch("sentinel.core.eventing.httpx.AsyncClient")
    @patch("sentinel.core.eventing.urljoin")
    @patch("sentinel.core.eventing.kering")
    @patch("sentinel.core.eventing.serdering.SerderKERI")
    @patch("sentinel.core.eventing.dbing.dgKey")
    @patch("sentinel.core.eventing.habbing.Habery")
    async def test_sync_server_key_state_fetch_receipts_from_witnesses(
        self,
        mock_habery_class,
        mock_dgkey,
        mock_serderkeri_class,
        mock_kering,
        mock_urljoin,
        mock_httpx_client_class,
    ):
        """Test fetching receipts from witnesses when wigs don't exist"""
        # Setup mocks
        mock_hab = Mock()
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]
        mock_serder = Mock()
        mock_serder.preb = b"test_preb"
        mock_serder.saidb = b"test_saidb"
        mock_kever.serder = mock_serder
        mock_hab.kever = mock_kever
        mock_hab.pre = "ETestPrefix123"

        mock_db = Mock()
        mock_db.getAes.return_value = b"existing_seal"
        mock_db.getWigs.return_value = None  # No wigs
        mock_db.getKelIter.return_value = [b"digest1"]
        mock_db.getEvt.return_value = b"event_raw_data"
        mock_hab.db = mock_db

        # Setup kering Schemes FIRST
        mock_kering.Schemes.http = "http"
        mock_kering.Schemes.https = "https"

        # Setup fetchUrls with proper string keys
        mock_hab.fetchUrls.return_value = {"http": "http://witness.example.com"}

        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_hby.db = mock_db  # Add db to hby
        mock_habery_class.return_value = mock_hby

        mock_dgkey.return_value = b"test_dgkey"

        # Setup SerderKERI
        mock_event_serder = Mock()
        mock_event_serder.sn = 1
        mock_serderkeri_class.return_value = mock_event_serder

        # Setup urljoin
        mock_urljoin.return_value = (
            "http://witness.example.com/receipts?pre=ETestPrefix123&sn=1"
        )

        # Setup httpx AsyncClient
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"receipt_content"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_httpx_client_class.return_value = mock_client

        # Setup psr.parseOne
        mock_psr = Mock()
        mock_hab.psr = mock_psr

        # Call function
        await sync_server_key_state(
            name=self.name,
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            essr=self.mock_essr,
        )

        # Verify fetchUrls was called
        mock_hab.fetchUrls.assert_called()

        # Verify urljoin was called
        mock_urljoin.assert_called_once()

        # Verify HTTP request was made
        mock_client.get.assert_called_once()

        # Verify psr.parseOne was called with receipt
        mock_psr.parseOne.assert_called_once()

    @patch("sentinel.core.eventing.kering")
    @patch("sentinel.core.eventing.serdering.SerderKERI")
    @patch("sentinel.core.eventing.dbing.dgKey")
    @patch("sentinel.core.eventing.habbing.Habery")
    async def test_sync_server_key_state_missing_witness_urls(
        self, mock_habery_class, mock_dgkey, mock_serderkeri_class, mock_kering
    ):
        """Test error when witness has no HTTP endpoints"""
        # Setup mocks
        mock_hab = Mock()
        mock_kever = Mock()
        mock_kever.wits = ["EWitness123"]
        mock_serder = Mock()
        mock_serder.preb = b"test_preb"
        mock_serder.saidb = b"test_saidb"
        mock_kever.serder = mock_serder
        mock_hab.kever = mock_kever
        mock_hab.pre = "ETestPrefix123"

        mock_db = Mock()
        mock_db.getAes.return_value = b"existing_seal"
        mock_db.getWigs.return_value = None  # No wigs
        mock_db.getKelIter.return_value = [b"digest1"]
        mock_db.getEvt.return_value = b"event_raw_data"
        mock_hab.db = mock_db

        # Setup fetchUrls to return None (no URLs)
        mock_hab.fetchUrls.return_value = None

        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_hby.db = mock_db  # Add db to hby
        mock_habery_class.return_value = mock_hby

        mock_dgkey.return_value = b"test_dgkey"

        # Setup SerderKERI
        mock_event_serder = Mock()
        mock_event_serder.sn = 1
        mock_serderkeri_class.return_value = mock_event_serder

        # Setup kering Schemes
        mock_kering.Schemes.http = "http"
        mock_kering.Schemes.https = "https"
        mock_kering.MissingEntryError = Exception

        # Call function and expect error
        with self.assertRaises(Exception) as context:
            await sync_server_key_state(
                name=self.name,
                alias=self.alias,
                base=self.base,
                bran=self.bran,
                essr=self.mock_essr,
            )

        # Verify error message
        self.assertIn("unable to query witness", str(context.exception))

    @patch("sentinel.core.eventing.parsing.Parser")
    @patch("sentinel.core.eventing.eventing.Kevery")
    @patch("sentinel.core.eventing.coring.Seqner")
    @patch("sentinel.core.eventing.serdering.SerderKERI")
    @patch("sentinel.core.eventing.MultipartDecoder")
    @patch("sentinel.core.eventing.dbing.dgKey")
    @patch("sentinel.core.eventing.habbing.Habery")
    async def test_sync_server_key_state_fetch_from_delegator_success(
        self,
        mock_habery_class,
        mock_dgkey,
        mock_multipart_decoder_class,
        mock_serderkeri_class,
        mock_seqner_class,
        mock_kevery_class,
        mock_parser_class,
    ):
        """Test fetching seal from delegator when seal doesn't exist"""
        # Setup mocks
        mock_hab = Mock()
        mock_kever = Mock()
        mock_kever.delpre = "EDelegator123"
        mock_kever.prefixer = Mock()
        mock_kever.prefixer.qb64b = b"test_prefixer"
        mock_serder = Mock()
        mock_serder.preb = b"test_preb"
        mock_serder.saidb = b"test_saidb"
        mock_kever.serder = mock_serder
        mock_hab.kever = mock_kever
        mock_hab.pre = "ETestPrefix123"

        mock_db = Mock()
        mock_db.getAes.return_value = None  # No seal
        mock_db.getWigs.return_value = [b"existing_wig"]  # Wigs exist
        mock_db.getKelIter.return_value = [b"digest1"]
        mock_db.getEvt.return_value = b"event_raw_data"
        mock_db.fetchLastSealingEventByEventSeal.return_value = Mock(
            sn=5, saidb=b"delegator_said"
        )
        mock_hab.db = mock_db

        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_hby.kevers = {"EDelegator123": Mock(sn=10)}
        mock_hby.db = mock_db  # Add db to hby
        mock_habery_class.return_value = mock_hby

        mock_dgkey.return_value = b"test_dgkey"

        # Setup multipart response
        mock_response = Mock()
        mock_response.status_code = 200

        # Create mock parts
        doc_part = Mock()
        doc_part.headers = {b"content-disposition": b'form-data; name="doc"'}
        doc_data = {"key_state": {"s": "a"}}  # hex for 10
        doc_part.content = json.dumps(doc_data).encode("utf-8")

        cesr_part = Mock()
        cesr_part.headers = {b"content-disposition": b'form-data; name="cesr"'}
        cesr_part.content = b"cesr_stream_data"

        mock_decoder = Mock()
        mock_decoder.parts = [doc_part, cesr_part]
        mock_multipart_decoder_class.from_response.return_value = mock_decoder

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Setup SerderKERI
        mock_event_serder = Mock()
        mock_event_serder.pre = "ETestPrefix123"
        mock_event_serder.snh = "1"
        mock_event_serder.said = "ESaid123"
        mock_serderkeri_class.return_value = mock_event_serder

        # Setup Seqner
        mock_seqner = Mock()
        mock_seqner.qb64b = b"seqner_qb64b"
        mock_seqner_class.return_value = mock_seqner

        # Setup Kevery and Parser
        mock_kvy = Mock()
        mock_kevery_class.return_value = mock_kvy
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser

        # Call function
        await sync_server_key_state(
            name=self.name,
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            essr=self.mock_essr,
        )

        # Verify API request was made to fetch delegator
        self.mock_essr.request.assert_called_once()
        call_args = self.mock_essr.request.call_args
        self.assertIn("EDelegator123", call_args[0][0])

        # Verify multipart decoder was used
        mock_multipart_decoder_class.from_response.assert_called_once_with(
            mock_response
        )

        # Verify Kevery was created
        mock_kevery_class.assert_called_once()

        # Verify Parser was used
        mock_parser.parse.assert_called_once()

        # Verify setAes was called to store the seal
        mock_db.setAes.assert_called()

    @patch("sentinel.core.eventing.parsing.Parser")
    @patch("sentinel.core.eventing.eventing.Kevery")
    @patch("sentinel.core.eventing.MultipartDecoder")
    @patch("sentinel.core.eventing.dbing.dgKey")
    @patch("sentinel.core.eventing.habbing.Habery")
    async def test_sync_server_key_state_delegator_sequence_mismatch(
        self,
        mock_habery_class,
        mock_dgkey,
        mock_multipart_decoder_class,
        mock_kevery_class,
        mock_parser_class,
    ):
        """Test error when delegator sequence number doesn't match"""
        # Setup mocks
        mock_hab = Mock()
        mock_kever = Mock()
        mock_kever.delpre = "EDelegator123"
        mock_serder = Mock()
        mock_serder.preb = b"test_preb"
        mock_serder.saidb = b"test_saidb"
        mock_kever.serder = mock_serder
        mock_hab.kever = mock_kever

        mock_db = Mock()
        mock_db.getAes.return_value = None  # No seal
        mock_hab.db = mock_db

        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_hby.kevers = {"EDelegator123": Mock(sn=5)}  # Different SN
        mock_habery_class.return_value = mock_hby

        mock_dgkey.return_value = b"test_dgkey"

        # Setup multipart response with different SN
        mock_response = Mock()
        mock_response.status_code = 200

        doc_part = Mock()
        doc_part.headers = {b"content-disposition": b'form-data; name="doc"'}
        doc_data = {
            "key_state": {"s": "a"}  # hex for 10, different from kevers sn of 5
        }
        doc_part.content = json.dumps(doc_data).encode("utf-8")

        cesr_part = Mock()
        cesr_part.headers = {b"content-disposition": b'form-data; name="cesr"'}
        cesr_part.content = b"cesr_stream_data"

        mock_decoder = Mock()
        mock_decoder.parts = [doc_part, cesr_part]
        mock_multipart_decoder_class.from_response.return_value = mock_decoder

        self.mock_essr.request = AsyncMock(return_value=mock_response)

        # Setup Kevery and Parser
        mock_kvy = Mock()
        mock_kevery_class.return_value = mock_kvy
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser

        # Call function and expect ValueError
        with self.assertRaises(ValueError) as context:
            await sync_server_key_state(
                name=self.name,
                alias=self.alias,
                base=self.base,
                bran=self.bran,
                essr=self.mock_essr,
            )

        # Verify error message
        self.assertIn("different current sequence number", str(context.exception))

    @patch("sentinel.core.eventing.dbing.dgKey")
    @patch("sentinel.core.eventing.habbing.Habery")
    async def test_sync_server_key_state_skips_none_events(
        self, mock_habery_class, mock_dgkey
    ):
        """Test that None events are skipped during KEL iteration"""
        # Setup mocks
        mock_hab = Mock()
        mock_kever = Mock()
        mock_kever.wits = []  # No witnesses
        mock_serder = Mock()
        mock_serder.preb = b"test_preb"
        mock_serder.saidb = b"test_saidb"
        mock_kever.serder = mock_serder
        mock_hab.kever = mock_kever
        mock_hab.pre = "ETestPrefix123"

        mock_db = Mock()
        mock_db.getAes.return_value = b"existing_seal"
        mock_db.getWigs.return_value = None  # No wigs
        mock_db.getKelIter.return_value = [b"digest1", b"digest2"]
        mock_db.getEvt.side_effect = [None, None]  # Both return None
        mock_hab.db = mock_db

        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_hby.db = mock_db  # Add db to hby
        mock_habery_class.return_value = mock_hby

        mock_dgkey.return_value = b"test_dgkey"

        # Call function (should not raise error, just skip None events)
        await sync_server_key_state(
            name=self.name,
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            essr=self.mock_essr,
        )

        # Verify getEvt was called multiple times
        self.assertEqual(mock_db.getEvt.call_count, 2)


if __name__ == "__main__":
    unittest.main()
