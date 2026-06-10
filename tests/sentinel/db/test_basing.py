# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.db.basing module
"""

import tempfile
import unittest
from unittest.mock import Mock, patch

from sentinel.db.basing import SentinelBaser


class TestSentinelBaser(unittest.TestCase):
    """Test cases for SentinelBaser class"""

    def test_class_attributes(self):
        """Test that class attributes are correctly defined"""
        self.assertEqual(SentinelBaser.TailDirPath, "keri/hk")
        self.assertEqual(SentinelBaser.AltTailDirPath, ".keri/hk")
        self.assertEqual(SentinelBaser.TempPrefix, "hk")

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_init_default_parameters(self, mock_super_init):
        """Test initialization with default parameters"""
        mock_super_init.return_value = None

        baser = SentinelBaser()

        # Verify watched_poll initialized to None
        self.assertIsNone(baser.watched_poll)

        # Verify parent __init__ called with defaults
        mock_super_init.assert_called_once_with(
            name="sentinel", headDirPath=None, reopen=True
        )

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_init_custom_name(self, mock_super_init):
        """Test initialization with custom name"""
        mock_super_init.return_value = None

        baser = SentinelBaser(name="custom_sentinel")

        # Verify watched_poll initialized to None
        self.assertIsNone(baser.watched_poll)

        # Verify parent __init__ called with custom name
        mock_super_init.assert_called_once_with(
            name="custom_sentinel", headDirPath=None, reopen=True
        )

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_init_custom_head_dir_path(self, mock_super_init):
        """Test initialization with custom headDirPath"""
        mock_super_init.return_value = None
        custom_path = "/custom/path/to/db"

        baser = SentinelBaser(headDirPath=custom_path)

        # Verify watched_poll initialized to None
        self.assertIsNone(baser.watched_poll)

        # Verify parent __init__ called with custom path
        mock_super_init.assert_called_once_with(
            name="sentinel", headDirPath=custom_path, reopen=True
        )

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_init_reopen_false(self, mock_super_init):
        """Test initialization with reopen=False"""
        mock_super_init.return_value = None

        baser = SentinelBaser(reopen=False)

        # Verify watched_poll initialized to None
        self.assertIsNone(baser.watched_poll)

        # Verify parent __init__ called with reopen=False
        mock_super_init.assert_called_once_with(
            name="sentinel", headDirPath=None, reopen=False
        )

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_init_all_custom_parameters(self, mock_super_init):
        """Test initialization with all custom parameters"""
        mock_super_init.return_value = None
        custom_path = "/custom/path"
        custom_name = "test_sentinel"

        baser = SentinelBaser(name=custom_name, headDirPath=custom_path, reopen=False)

        # Verify watched_poll initialized to None
        self.assertIsNone(baser.watched_poll)

        # Verify parent __init__ called with all custom params
        mock_super_init.assert_called_once_with(
            name=custom_name, headDirPath=custom_path, reopen=False
        )

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_init_with_extra_kwargs(self, mock_super_init):
        """Test initialization with extra keyword arguments"""
        mock_super_init.return_value = None

        baser = SentinelBaser(
            name="test",
            headDirPath="/test/path",
            reopen=True,
            readonly=True,
            mdbEnvFlags=0x20000,
        )

        # Verify watched_poll initialized to None
        self.assertIsNone(baser.watched_poll)

        # Verify parent __init__ called with all params including extras
        mock_super_init.assert_called_once_with(
            name="test",
            headDirPath="/test/path",
            reopen=True,
            readonly=True,
            mdbEnvFlags=0x20000,
        )

    @patch("sentinel.db.basing.koming.Komer")
    @patch("sentinel.db.basing.subing.CesrSuber")
    @patch("sentinel.db.basing.dbing.LMDBer.reopen")
    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_reopen(self, mock_super_init, mock_super_reopen, mock_cesr_suber_class, mock_komer_class):
        """Test reopen method"""
        mock_super_init.return_value = None
        mock_env = Mock()
        mock_super_reopen.return_value = mock_env

        mock_suber = Mock()
        mock_cesr_suber_class.return_value = mock_suber
        mock_komer = Mock()
        mock_komer_class.return_value = mock_komer

        # Create baser
        baser = SentinelBaser()
        baser.env = mock_env  # Add env attribute

        # Verify watched_poll is None initially
        self.assertIsNone(baser.watched_poll)

        # Call reopen
        result = baser.reopen()

        # Verify parent reopen was called
        mock_super_reopen.assert_called_once_with()

        # Verify CesrSuber was called twice (for watched_poll and watched_scan_index)
        self.assertEqual(mock_cesr_suber_class.call_count, 2)

        # Verify first CesrSuber call was for watched_poll
        first_call_kwargs = mock_cesr_suber_class.call_args_list[0][1]
        self.assertEqual(first_call_kwargs["db"], baser)
        self.assertEqual(first_call_kwargs["subkey"], "watched.")

        # Verify klas parameter is core.Dater
        from keri.core import coring

        self.assertEqual(first_call_kwargs["klas"], coring.Dater)

        # Verify watched_poll was set
        self.assertEqual(baser.watched_poll, mock_suber)

        # Verify return value is env
        self.assertEqual(result, mock_env)

    @patch("sentinel.db.basing.subing.CesrSuber")
    @patch("sentinel.db.basing.dbing.LMDBer.reopen")
    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_reopen_with_kwargs(
        self, mock_super_init, mock_super_reopen, mock_cesr_suber_class
    ):
        """Test reopen method with keyword arguments"""
        mock_super_init.return_value = None
        mock_env = Mock()
        mock_super_reopen.return_value = mock_env

        mock_suber = Mock()
        mock_cesr_suber_class.return_value = mock_suber

        # Create baser
        baser = SentinelBaser()
        baser.env = mock_env  # Add env attribute

        # Call reopen with kwargs
        result = baser.reopen(readonly=True)

        # Verify parent reopen was called with kwargs
        mock_super_reopen.assert_called_once_with(readonly=True)

        # Verify watched_poll was set
        self.assertEqual(baser.watched_poll, mock_suber)

        # Verify return value is env
        self.assertEqual(result, mock_env)

    @patch("sentinel.db.basing.koming.Komer")
    @patch("sentinel.db.basing.subing.CesrSuber")
    @patch("sentinel.db.basing.dbing.LMDBer.reopen")
    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_reopen_replaces_existing_watched_poll(
        self, mock_super_init, mock_super_reopen, mock_cesr_suber_class, mock_komer_class
    ):
        """Test that reopen replaces existing watched_poll"""
        mock_super_init.return_value = None
        mock_env = Mock()
        mock_super_reopen.return_value = mock_env

        mock_suber1 = Mock()
        mock_suber2 = Mock()
        mock_suber3 = Mock()
        mock_suber4 = Mock()
        # Each reopen creates 2 CesrSuber instances (watched_poll and watched_scan_index)
        mock_cesr_suber_class.side_effect = [mock_suber1, mock_suber2, mock_suber3, mock_suber4]
        mock_komer = Mock()
        mock_komer_class.return_value = mock_komer

        # Create baser
        baser = SentinelBaser()
        baser.env = mock_env  # Add env attribute

        # First reopen
        baser.reopen()
        self.assertEqual(baser.watched_poll, mock_suber1)

        # Second reopen
        baser.reopen()
        self.assertEqual(baser.watched_poll, mock_suber3)

        # Verify CesrSuber was called 4 times (2 per reopen)
        self.assertEqual(mock_cesr_suber_class.call_count, 4)

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_inheritance(self, mock_super_init):
        """Test that SentinelBaser inherits from LMDBer"""
        mock_super_init.return_value = None
        from keri.db import dbing

        baser = SentinelBaser()

        # Verify inheritance
        self.assertIsInstance(baser, dbing.LMDBer)

    @patch("sentinel.db.basing.koming.Komer")
    @patch("sentinel.db.basing.subing.CesrSuber")
    @patch("sentinel.db.basing.dbing.LMDBer.reopen")
    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_watched_poll_suber_configuration(
        self, mock_super_init, mock_super_reopen, mock_cesr_suber_class, mock_komer_class
    ):
        """Test watched_poll suber is configured with correct subkey"""
        mock_super_init.return_value = None
        mock_env = Mock()
        mock_super_reopen.return_value = mock_env

        mock_suber = Mock()
        mock_cesr_suber_class.return_value = mock_suber
        mock_komer = Mock()
        mock_komer_class.return_value = mock_komer

        # Create baser
        baser = SentinelBaser()
        baser.env = mock_env  # Add env attribute
        baser.reopen()

        # Verify subkey is 'watched.' (with dot suffix) - check first call
        call_kwargs = mock_cesr_suber_class.call_args_list[0][1]
        self.assertEqual(call_kwargs["subkey"], "watched.")
        self.assertTrue(call_kwargs["subkey"].endswith("."))

    @patch("sentinel.db.basing.dbing.LMDBer.__init__")
    def test_init_preserves_watched_poll_none(self, mock_super_init):
        """Test that __init__ sets watched_poll to None before parent init"""
        mock_super_init.return_value = None

        baser = SentinelBaser()

        # Verify watched_poll is None after init
        self.assertIsNone(baser.watched_poll)

        # Verify this happens even if parent init would set it
        # (watched_poll should only be set in reopen)
        self.assertIsNone(baser.watched_poll)


class TestSentinelBaserIntegration(unittest.TestCase):
    """Integration tests for SentinelBaser with actual database operations"""

    def setUp(self):
        """Set up test fixtures with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil

        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def test_create_and_reopen_actual_database(self):
        """Test creating an actual database and reopening it"""
        # Create baser with temp directory
        baser = SentinelBaser(
            name="test_sentinel", headDirPath=self.temp_dir, reopen=True
        )

        try:
            # Verify watched_poll was created during reopen
            self.assertIsNotNone(baser.watched_poll)

            # Verify it's the correct type
            from keri.db import subing

            self.assertIsInstance(baser.watched_poll, subing.CesrSuber)

            # Verify it has a database reference
            self.assertEqual(baser.watched_poll.db, baser)

        finally:
            # Clean up
            try:
                baser.close()
            except Exception:
                pass

    def test_reopen_updates_watched_poll(self):
        """Test that reopening updates watched_poll"""
        # Create baser with temp directory
        baser = SentinelBaser(
            name="test_sentinel", headDirPath=self.temp_dir, reopen=False
        )

        try:
            # Initially watched_poll is None (reopen=False)
            self.assertIsNone(baser.watched_poll)

            # Call reopen
            env = baser.reopen()

            # Verify watched_poll is now set
            self.assertIsNotNone(baser.watched_poll)

            # Verify env is returned
            self.assertIsNotNone(env)

            # Verify it's the correct type
            from keri.db import subing

            self.assertIsInstance(baser.watched_poll, subing.CesrSuber)

        finally:
            # Clean up
            try:
                baser.close()
            except Exception:
                pass

    def test_watched_poll_operations(self):
        """Test basic operations on watched_poll suber"""
        # Create baser with temp directory
        baser = SentinelBaser(
            name="test_sentinel", headDirPath=self.temp_dir, reopen=True
        )

        try:
            from keri.core import coring
            from datetime import datetime, timezone

            # Create a Dater object
            now = datetime.now(timezone.utc)
            dater = coring.Dater(dts=now.isoformat())

            # Store in watched_poll
            baser.watched_poll.pin(keys=("test_key",), val=dater)

            # Retrieve from watched_poll
            retrieved = baser.watched_poll.get(keys=("test_key",))

            # Verify retrieved value
            self.assertIsNotNone(retrieved)
            self.assertIsInstance(retrieved, coring.Dater)
            self.assertEqual(retrieved.dts, dater.dts)

        finally:
            # Clean up
            try:
                baser.close()
            except Exception:
                pass

    def test_multiple_keys_in_watched_poll(self):
        """Test storing and retrieving multiple keys in watched_poll"""
        # Create baser with temp directory
        baser = SentinelBaser(
            name="test_sentinel", headDirPath=self.temp_dir, reopen=True
        )

        try:
            from keri.core import coring
            import time

            # Create multiple Dater objects using current time
            dater1 = coring.Dater()
            time.sleep(0.01)  # Small delay to ensure different timestamps
            dater2 = coring.Dater()

            # Store multiple entries
            baser.watched_poll.pin(keys=("key1",), val=dater1)
            baser.watched_poll.pin(keys=("key2",), val=dater2)

            # Retrieve both
            retrieved1 = baser.watched_poll.get(keys=("key1",))
            retrieved2 = baser.watched_poll.get(keys=("key2",))

            # Verify both values
            self.assertEqual(retrieved1.dts, dater1.dts)
            self.assertEqual(retrieved2.dts, dater2.dts)
            self.assertNotEqual(dater1.dts, dater2.dts)

        finally:
            # Clean up
            try:
                baser.close()
            except Exception:
                pass

    def test_database_persistence(self):
        """Test that data persists across reopens"""
        from keri.core import coring

        # Create and populate database
        baser1 = SentinelBaser(
            name="test_sentinel", headDirPath=self.temp_dir, reopen=True
        )

        dater_dts = None
        try:
            dater = coring.Dater()
            dater_dts = dater.dts
            baser1.watched_poll.pin(keys=("persist_test",), val=dater)
        finally:
            baser1.close()

        # Reopen database and verify data persists
        baser2 = SentinelBaser(
            name="test_sentinel", headDirPath=self.temp_dir, reopen=True
        )

        try:
            retrieved = baser2.watched_poll.get(keys=("persist_test",))
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.dts, dater_dts)
        finally:
            baser2.close()


if __name__ == "__main__":
    unittest.main()
