# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.app.sentineling module
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock

from sentinel.app.sentineling import setup_local, setup_hk, UnsupportedOperation


class TestSetupLocal(unittest.TestCase):
    """Test cases for setup_local function"""

    def test_setup_local_raises_unsupported_operation(self):
        """Test that setup_local raises UnsupportedOperation"""
        with self.assertRaises(UnsupportedOperation) as context:
            setup_local(
                name="test",
                alias="testalias",
                base="/tmp/test",
                bran="testbran",
                uxd=False,
                port=8080,
            )

        self.assertEqual(
            str(context.exception), "Local watcher configuration is not supported yet"
        )


class TestSetupHk(unittest.IsolatedAsyncioTestCase):
    """Test cases for setup_hk function"""

    def setUp(self):
        """Set up test fixtures"""
        self.name = "testsentinel"
        self.alias = "testalias"
        self.base = "/tmp/test"
        self.bran = "testbran"
        self.port = 8080

    @patch("sentinel.app.sentineling.sync_server_key_state", new_callable=AsyncMock)
    @patch("sentinel.app.sentineling.ObvsSocketListener")
    @patch("sentinel.app.sentineling.WatchedAdjudicationPoller")
    @patch("sentinel.app.sentineling.APIClient")
    @patch("sentinel.app.sentineling.HealthKERIConfig")
    @patch("sentinel.app.sentineling.SentinelBaser")
    @patch("sentinel.app.sentineling.habbing.Habery")
    async def test_setup_hk_without_uxd(
        self,
        mock_habery_class,
        mock_baser_class,
        mock_config_class,
        mock_api_client_class,
        mock_poller_class,
        mock_socket_listener_class,
        mock_sync_server,
    ):
        """Test setup_hk without uxd flag returns only poller"""
        # Setup mocks
        mock_hab = Mock()
        mock_hab.pre = "ETestAIDPrefix123"
        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_habery_class.return_value = mock_hby

        mock_db = Mock()
        mock_baser_class.return_value = mock_db

        mock_config = Mock()
        mock_config.protected_url = "https://api.example.com"
        mock_config.api_aid = "EAPIRoot123"
        mock_config_class.get_instance.return_value = mock_config

        mock_essr = Mock()
        mock_api_client_class.return_value = mock_essr

        mock_poller = Mock()
        mock_poller_class.return_value = mock_poller

        # Call setup_hk without uxd
        result = await setup_hk(
            name=self.name,
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            uxd=False,
            port=self.port,
        )

        # Verify Habery initialization with sentinel_name
        sentinel_name = f"{self.name}-sentinel"
        mock_habery_class.assert_called_once_with(
            name=sentinel_name, base=self.base, bran=self.bran
        )

        # Verify habByName called with sentinel_alias
        sentinel_alias = f"{self.alias}-sentinel"
        mock_hby.habByName.assert_called_once_with(sentinel_alias)

        # Verify SentinelBaser initialization
        mock_baser_class.assert_called_once_with(name=self.name, headDirPath=self.base)

        # Verify HealthKERIConfig usage
        mock_config_class.get_instance.assert_called_once()

        # Verify APIClient initialization
        mock_api_client_class.assert_called_once_with(
            url=mock_config.protected_url,
            root=mock_config.api_aid,
            hby=mock_hby,
            hab=mock_hab,
        )

        # Verify sync_server_key_state was called
        mock_sync_server.assert_called_once_with(
            self.name, self.alias, self.base, self.bran, mock_essr
        )

        # Verify WatchedAdjudicationPoller initialization
        mock_poller_class.assert_called_once_with(
            hby=mock_hby, essr=mock_essr, db=mock_db, poll_interval=15.0
        )

        # Verify ObvsSocketListener was NOT created
        mock_socket_listener_class.assert_not_called()

        # Verify result contains only poller
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], mock_poller)

    @patch("sentinel.app.sentineling.sync_server_key_state", new_callable=AsyncMock)
    @patch("sentinel.app.sentineling.ObvsSocketListener")
    @patch("sentinel.app.sentineling.WatchedAdjudicationPoller")
    @patch("sentinel.app.sentineling.APIClient")
    @patch("sentinel.app.sentineling.HealthKERIConfig")
    @patch("sentinel.app.sentineling.SentinelBaser")
    @patch("sentinel.app.sentineling.habbing.Habery")
    async def test_setup_hk_with_uxd(
        self,
        mock_habery_class,
        mock_baser_class,
        mock_config_class,
        mock_api_client_class,
        mock_poller_class,
        mock_socket_listener_class,
        mock_sync_server,
    ):
        """Test setup_hk with uxd flag returns both poller and socket listener"""
        # Setup mocks
        mock_hab = Mock()
        mock_hab.pre = "ETestAIDPrefix123"
        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_habery_class.return_value = mock_hby

        mock_db = Mock()
        mock_baser_class.return_value = mock_db

        mock_config = Mock()
        mock_config.protected_url = "https://api.example.com"
        mock_config.api_aid = "EAPIRoot123"
        mock_config_class.get_instance.return_value = mock_config

        mock_essr = Mock()
        mock_api_client_class.return_value = mock_essr

        mock_poller = Mock()
        mock_poller_class.return_value = mock_poller

        mock_socket_listener = Mock()
        mock_socket_listener_class.return_value = mock_socket_listener

        # Call setup_hk with uxd=True
        result = await setup_hk(
            name=self.name,
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            uxd=True,
            port=self.port,
        )

        # Verify Habery initialization with sentinel_name
        sentinel_name = f"{self.name}-sentinel"
        mock_habery_class.assert_called_once_with(
            name=sentinel_name, base=self.base, bran=self.bran
        )

        # Verify habByName called with sentinel_alias
        sentinel_alias = f"{self.alias}-sentinel"
        mock_hby.habByName.assert_called_once_with(sentinel_alias)

        # Verify SentinelBaser initialization
        mock_baser_class.assert_called_once_with(name=self.name, headDirPath=self.base)

        # Verify HealthKERIConfig usage
        mock_config_class.get_instance.assert_called_once()

        # Verify APIClient initialization
        mock_api_client_class.assert_called_once_with(
            url=mock_config.protected_url,
            root=mock_config.api_aid,
            hby=mock_hby,
            hab=mock_hab,
        )

        # Verify sync_server_key_state was called
        mock_sync_server.assert_called_once_with(
            self.name, self.alias, self.base, self.bran, mock_essr
        )

        # Verify WatchedAdjudicationPoller initialization
        mock_poller_class.assert_called_once_with(
            hby=mock_hby, essr=mock_essr, db=mock_db, poll_interval=15.0
        )

        # Verify ObvsSocketListener initialization with correct socket path
        expected_socket_path = f"/tmp/sentinel_{mock_hab.pre}.sock"
        mock_socket_listener_class.assert_called_once_with(
            hby=mock_hby,
            essr=mock_essr,
            db=mock_db,
            socket_path=expected_socket_path,
            poll_interval=0.5,
        )

        # Verify result contains both services
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], mock_poller)
        self.assertEqual(result[1], mock_socket_listener)

    @patch("sentinel.app.sentineling.sync_server_key_state", new_callable=AsyncMock)
    @patch("sentinel.app.sentineling.ObvsSocketListener")
    @patch("sentinel.app.sentineling.WatchedAdjudicationPoller")
    @patch("sentinel.app.sentineling.APIClient")
    @patch("sentinel.app.sentineling.HealthKERIConfig")
    @patch("sentinel.app.sentineling.SentinelBaser")
    @patch("sentinel.app.sentineling.habbing.Habery")
    async def test_setup_hk_alias_not_found(
        self,
        mock_habery_class,
        mock_baser_class,
        mock_config_class,
        mock_api_client_class,
        mock_poller_class,
        mock_socket_listener_class,
        mock_sync_server,
    ):
        """Test setup_hk raises ValueError when alias is not found"""
        # Setup mocks - habByName returns None
        mock_hby = Mock()
        mock_hby.habByName.return_value = None
        mock_habery_class.return_value = mock_hby

        # Call setup_hk and expect ValueError
        with self.assertRaises(ValueError) as context:
            await setup_hk(
                name=self.name,
                alias=self.alias,
                base=self.base,
                bran=self.bran,
                uxd=False,
                port=self.port,
            )

        # Verify error message (updated to match new code)
        self.assertEqual(
            str(context.exception),
            f"Sentinel alias for '{self.alias}' not found in sentinel Habery '{self.name}'",
        )

        # Verify habByName was called with sentinel_alias
        sentinel_alias = f"{self.alias}-sentinel"
        mock_hby.habByName.assert_called_once_with(sentinel_alias)

        # Verify subsequent initialization was not called
        mock_baser_class.assert_not_called()
        mock_config_class.get_instance.assert_not_called()
        mock_api_client_class.assert_not_called()
        mock_sync_server.assert_not_called()
        mock_poller_class.assert_not_called()
        mock_socket_listener_class.assert_not_called()

    @patch("sentinel.app.sentineling.sync_server_key_state", new_callable=AsyncMock)
    @patch("sentinel.app.sentineling.ObvsSocketListener")
    @patch("sentinel.app.sentineling.WatchedAdjudicationPoller")
    @patch("sentinel.app.sentineling.APIClient")
    @patch("sentinel.app.sentineling.HealthKERIConfig")
    @patch("sentinel.app.sentineling.SentinelBaser")
    @patch("sentinel.app.sentineling.habbing.Habery")
    async def test_setup_hk_socket_path_uses_hab_pre(
        self,
        mock_habery_class,
        mock_baser_class,
        mock_config_class,
        mock_api_client_class,
        mock_poller_class,
        mock_socket_listener_class,
        mock_sync_server,
    ):
        """Test that socket path uses hab.pre instead of name parameter"""
        # Setup mocks with specific pre value
        mock_hab = Mock()
        mock_hab.pre = "ECustomPrefix456"
        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_habery_class.return_value = mock_hby

        mock_db = Mock()
        mock_baser_class.return_value = mock_db

        mock_config = Mock()
        mock_config.protected_url = "https://api.example.com"
        mock_config.api_aid = "EAPIRoot123"
        mock_config_class.get_instance.return_value = mock_config

        mock_essr = Mock()
        mock_api_client_class.return_value = mock_essr

        mock_poller = Mock()
        mock_poller_class.return_value = mock_poller

        mock_socket_listener = Mock()
        mock_socket_listener_class.return_value = mock_socket_listener

        # Call setup_hk with uxd=True
        await setup_hk(
            name="different_name",
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            uxd=True,
            port=self.port,
        )

        # Verify socket path uses hab.pre, not name
        expected_socket_path = "/tmp/sentinel_ECustomPrefix456.sock"
        mock_socket_listener_class.assert_called_once()
        call_kwargs = mock_socket_listener_class.call_args[1]
        self.assertEqual(call_kwargs["socket_path"], expected_socket_path)

    @patch("sentinel.app.sentineling.sync_server_key_state", new_callable=AsyncMock)
    @patch("sentinel.app.sentineling.ObvsSocketListener")
    @patch("sentinel.app.sentineling.WatchedAdjudicationPoller")
    @patch("sentinel.app.sentineling.APIClient")
    @patch("sentinel.app.sentineling.HealthKERIConfig")
    @patch("sentinel.app.sentineling.SentinelBaser")
    @patch("sentinel.app.sentineling.habbing.Habery")
    async def test_setup_hk_returns_services_list_type(
        self,
        mock_habery_class,
        mock_baser_class,
        mock_config_class,
        mock_api_client_class,
        mock_poller_class,
        mock_socket_listener_class,
        mock_sync_server,
    ):
        """Test that setup_hk returns a list"""
        # Setup mocks
        mock_hab = Mock()
        mock_hab.pre = "ETestAIDPrefix123"
        mock_hby = Mock()
        mock_hby.habByName.return_value = mock_hab
        mock_habery_class.return_value = mock_hby

        mock_db = Mock()
        mock_baser_class.return_value = mock_db

        mock_config = Mock()
        mock_config.protected_url = "https://api.example.com"
        mock_config.api_aid = "EAPIRoot123"
        mock_config_class.get_instance.return_value = mock_config

        mock_essr = Mock()
        mock_api_client_class.return_value = mock_essr

        mock_poller = Mock()
        mock_poller_class.return_value = mock_poller

        # Call setup_hk
        result = await setup_hk(
            name=self.name,
            alias=self.alias,
            base=self.base,
            bran=self.bran,
            uxd=False,
            port=self.port,
        )

        # Verify return type
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)


if __name__ == "__main__":
    unittest.main()
