# -*- coding: utf-8 -*-
"""
Unit tests for sentinel.core.initializing module
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from sentinel.core.initializing import IssuerConfig, RegistrarConfig, SentinelConfig


class TestRegistrarConfig(unittest.TestCase):
    """Test cases for RegistrarConfig class"""

    def test_initialization_with_empty_data(self):
        """Test RegistrarConfig initialization with no data"""
        config = RegistrarConfig()

        self.assertEqual(config.aid, "")
        self.assertEqual(config.oobi, "")
        self.assertIsNone(config.url)
        self.assertIsNone(config.ipaddress)
        self.assertIsNone(config.endpoint)

    def test_initialization_with_data(self):
        """Test RegistrarConfig initialization with data"""
        data = {
            "aid": "ERegistrarAID123",
            "oobi": "http://registrar.example.com/oobi",
            "url": "http://registrar.example.com/api",
            "ipaddress": "10.0.0.1",
            "endpoint": "192.168.1.1:51820",
        }
        config = RegistrarConfig(data)

        self.assertEqual(config.aid, "ERegistrarAID123")
        self.assertEqual(config.oobi, "http://registrar.example.com/oobi")
        self.assertEqual(config.url, "http://registrar.example.com/api")
        self.assertEqual(config.ipaddress, "10.0.0.1")
        self.assertEqual(config.endpoint, "192.168.1.1:51820")

    def test_aid_property_getter_default(self):
        """Test aid property returns empty string by default"""
        config = RegistrarConfig()
        self.assertEqual(config.aid, "")

    def test_aid_property_setter(self):
        """Test aid property setter"""
        config = RegistrarConfig()
        config.aid = "ENewAID456"
        self.assertEqual(config.aid, "ENewAID456")

    def test_oobi_property_getter_default(self):
        """Test oobi property returns empty string by default"""
        config = RegistrarConfig()
        self.assertEqual(config.oobi, "")

    def test_oobi_property_setter(self):
        """Test oobi property setter"""
        config = RegistrarConfig()
        config.oobi = "http://new.oobi.com"
        self.assertEqual(config.oobi, "http://new.oobi.com")

    def test_url_property_getter_default(self):
        """Test url property returns None by default"""
        config = RegistrarConfig()
        self.assertIsNone(config.url)

    def test_url_property_setter(self):
        """Test url property setter"""
        config = RegistrarConfig()
        config.url = "http://example.com/api"
        self.assertEqual(config.url, "http://example.com/api")

    def test_url_property_setter_none(self):
        """Test url property setter with None removes the key"""
        config = RegistrarConfig({"url": "http://example.com"})
        config.url = None
        self.assertIsNone(config.url)
        self.assertNotIn("url", config._data)

    def test_ipaddress_property_getter_default(self):
        """Test ipaddress property returns None by default"""
        config = RegistrarConfig()
        self.assertIsNone(config.ipaddress)

    def test_ipaddress_property_setter(self):
        """Test ipaddress property setter"""
        config = RegistrarConfig()
        config.ipaddress = "10.0.0.2"
        self.assertEqual(config.ipaddress, "10.0.0.2")

    def test_ipaddress_property_setter_none(self):
        """Test ipaddress property setter with None removes the key"""
        config = RegistrarConfig({"ipaddress": "10.0.0.1"})
        config.ipaddress = None
        self.assertIsNone(config.ipaddress)
        self.assertNotIn("ipaddress", config._data)

    def test_endpoint_property_getter_default(self):
        """Test endpoint property returns None by default"""
        config = RegistrarConfig()
        self.assertIsNone(config.endpoint)

    def test_endpoint_property_setter(self):
        """Test endpoint property setter"""
        config = RegistrarConfig()
        config.endpoint = "192.168.1.2:51821"
        self.assertEqual(config.endpoint, "192.168.1.2:51821")

    def test_endpoint_property_setter_none(self):
        """Test endpoint property setter with None removes the key"""
        config = RegistrarConfig({"endpoint": "192.168.1.1:51820"})
        config.endpoint = None
        self.assertIsNone(config.endpoint)
        self.assertNotIn("endpoint", config._data)


class TestIssuerConfig(unittest.TestCase):
    """Test cases for IssuerConfig class"""

    def test_initialization_with_empty_data(self):
        """Test IssuerConfig initialization with no data"""
        config = IssuerConfig()

        self.assertEqual(config.aid, "")
        self.assertEqual(config.oobi, "")

    def test_initialization_with_data(self):
        """Test IssuerConfig initialization with data"""
        data = {"aid": "EIssuerAID789", "oobi": "http://issuer.example.com/oobi"}
        config = IssuerConfig(data)

        self.assertEqual(config.aid, "EIssuerAID789")
        self.assertEqual(config.oobi, "http://issuer.example.com/oobi")

    def test_aid_property_getter_default(self):
        """Test aid property returns empty string by default"""
        config = IssuerConfig()
        self.assertEqual(config.aid, "")

    def test_aid_property_setter(self):
        """Test aid property setter"""
        config = IssuerConfig()
        config.aid = "ENewIssuerAID"
        self.assertEqual(config.aid, "ENewIssuerAID")

    def test_oobi_property_getter_default(self):
        """Test oobi property returns empty string by default"""
        config = IssuerConfig()
        self.assertEqual(config.oobi, "")

    def test_oobi_property_setter(self):
        """Test oobi property setter"""
        config = IssuerConfig()
        config.oobi = "http://new.issuer.oobi.com"
        self.assertEqual(config.oobi, "http://new.issuer.oobi.com")


class TestSentinelConfig(unittest.TestCase):
    """Test cases for SentinelConfig class"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures"""
        # Clean up temp directory recursively
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization_with_empty_data(self):
        """Test SentinelConfig initialization with no data"""
        config = SentinelConfig()

        self.assertIsInstance(config.registrar, RegistrarConfig)
        self.assertIsInstance(config.issuer, IssuerConfig)
        self.assertIsNone(config.name)
        self.assertIsNone(config.alias)
        self.assertIsNone(config.bran)
        self.assertEqual(config.base, "")
        self.assertFalse(config.local)
        self.assertFalse(config.uxd)
        self.assertEqual(config.export_dir, "/usr/local/sentinel")

    def test_initialization_with_data(self):
        """Test SentinelConfig initialization with data"""
        data = {
            "name": "test-db",
            "alias": "test-alias",
            "bran": "1234567890123456789012",
            "base": "/custom/base",
            "local": True,
            "uxd": True,
            "export_dir": "/custom/export",
            "registrar": {"aid": "EAID123", "oobi": "http://reg.com"},
            "issuer": {"aid": "EISS456", "oobi": "http://iss.com"},
        }
        config = SentinelConfig(data)

        self.assertEqual(config.name, "test-db")
        self.assertEqual(config.alias, "test-alias")
        self.assertEqual(config.bran, "1234567890123456789012")
        self.assertEqual(config.base, "/custom/base")
        self.assertTrue(config.local)
        self.assertTrue(config.uxd)
        self.assertEqual(config.export_dir, "/custom/export")
        self.assertEqual(config.registrar.aid, "EAID123")
        self.assertEqual(config.issuer.aid, "EISS456")

    def test_load_valid_yaml_file(self):
        """Test loading configuration from a valid YAML file"""
        config_file = Path(self.temp_dir) / "test_config.yaml"
        config_data = {
            "name": "loaded-db",
            "alias": "loaded-alias",
            "registrar": {"aid": "ELOAD123", "oobi": "http://load.com"},
        }

        with open(config_file, "w") as f:
            yaml.safe_dump(config_data, f)

        config = SentinelConfig.load(str(config_file))

        self.assertEqual(config.name, "loaded-db")
        self.assertEqual(config.alias, "loaded-alias")
        self.assertEqual(config.registrar.aid, "ELOAD123")
        self.assertEqual(config.registrar.oobi, "http://load.com")

    def test_load_empty_yaml_file(self):
        """Test loading configuration from an empty YAML file"""
        config_file = Path(self.temp_dir) / "empty_config.yaml"

        with open(config_file, "w") as f:
            f.write("")

        config = SentinelConfig.load(str(config_file))

        self.assertIsInstance(config, SentinelConfig)
        self.assertIsNone(config.name)

    def test_load_nonexistent_file(self):
        """Test loading configuration from a nonexistent file raises FileNotFoundError"""
        config_file = Path(self.temp_dir) / "nonexistent.yaml"

        with self.assertRaises(FileNotFoundError) as context:
            SentinelConfig.load(str(config_file))

        self.assertIn("Configuration file not found", str(context.exception))

    def test_load_invalid_yaml_file(self):
        """Test loading configuration from an invalid YAML file raises YAMLError"""
        config_file = Path(self.temp_dir) / "invalid.yaml"

        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [")

        with self.assertRaises(yaml.YAMLError):
            SentinelConfig.load(str(config_file))

    def test_save_to_same_file(self):
        """Test saving configuration back to the same file it was loaded from"""
        config_file = Path(self.temp_dir) / "save_test.yaml"

        # Create initial config
        initial_data = {"name": "initial-db", "alias": "initial-alias"}
        with open(config_file, "w") as f:
            yaml.safe_dump(initial_data, f)

        # Load and modify
        config = SentinelConfig.load(str(config_file))
        config.name = "modified-db"
        config.registrar.aid = "EMODIFIED123"

        # Save
        config.save()

        # Reload and verify
        with open(config_file, "r") as f:
            saved_data = yaml.safe_load(f)

        self.assertEqual(saved_data["name"], "modified-db")
        self.assertEqual(saved_data["registrar"]["aid"], "EMODIFIED123")

    def test_save_to_different_file(self):
        """Test saving configuration to a different file"""
        config_file = Path(self.temp_dir) / "original.yaml"
        new_config_file = Path(self.temp_dir) / "new.yaml"

        # Create initial config
        initial_data = {"name": "original-db"}
        with open(config_file, "w") as f:
            yaml.safe_dump(initial_data, f)

        # Load and save to different file
        config = SentinelConfig.load(str(config_file))
        config.name = "new-db"
        config.save(str(new_config_file))

        # Verify new file exists and has correct data
        with open(new_config_file, "r") as f:
            saved_data = yaml.safe_load(f)

        self.assertEqual(saved_data["name"], "new-db")

        # Verify original file is unchanged
        with open(config_file, "r") as f:
            original_data = yaml.safe_load(f)

        self.assertEqual(original_data["name"], "original-db")

    def test_save_without_path_raises_error(self):
        """Test saving without a path when config wasn't loaded from file raises ValueError"""
        config = SentinelConfig()

        with self.assertRaises(ValueError) as context:
            config.save()

        self.assertIn("No config path specified", str(context.exception))

    def test_save_creates_parent_directories(self):
        """Test save creates parent directories if they don't exist"""
        nested_dir = Path(self.temp_dir) / "nested" / "dirs"
        config_file = nested_dir / "config.yaml"

        config = SentinelConfig({"name": "test-db"})
        config.save(str(config_file))

        self.assertTrue(config_file.exists())
        with open(config_file, "r") as f:
            saved_data = yaml.safe_load(f)

        self.assertEqual(saved_data["name"], "test-db")

    def test_name_property_getter_default(self):
        """Test name property returns None by default"""
        config = SentinelConfig()
        self.assertIsNone(config.name)

    def test_name_property_setter(self):
        """Test name property setter"""
        config = SentinelConfig()
        config.name = "new-db-name"
        self.assertEqual(config.name, "new-db-name")

    def test_name_property_setter_none(self):
        """Test name property setter with None removes the key"""
        config = SentinelConfig({"name": "old-name"})
        config.name = None
        self.assertIsNone(config.name)
        self.assertNotIn("name", config._data)

    def test_alias_property_getter_default(self):
        """Test alias property returns None by default"""
        config = SentinelConfig()
        self.assertIsNone(config.alias)

    def test_alias_property_setter(self):
        """Test alias property setter"""
        config = SentinelConfig()
        config.alias = "new-alias"
        self.assertEqual(config.alias, "new-alias")

    def test_alias_property_setter_none(self):
        """Test alias property setter with None removes the key"""
        config = SentinelConfig({"alias": "old-alias"})
        config.alias = None
        self.assertIsNone(config.alias)
        self.assertNotIn("alias", config._data)

    def test_bran_property_getter_default(self):
        """Test bran property returns None by default"""
        config = SentinelConfig()
        self.assertIsNone(config.bran)

    def test_bran_property_getter_with_bran_key(self):
        """Test bran property with 'bran' key"""
        config = SentinelConfig({"bran": "1234567890123456789012"})
        self.assertEqual(config.bran, "1234567890123456789012")

    def test_bran_property_getter_with_passcode_key(self):
        """Test bran property with 'passcode' key (legacy support)"""
        config = SentinelConfig({"passcode": "1234567890123456789012"})
        self.assertEqual(config.bran, "1234567890123456789012")

    def test_bran_property_getter_prefers_bran_over_passcode(self):
        """Test bran property prefers 'bran' key over 'passcode' when both exist"""
        config = SentinelConfig({"bran": "bran_value", "passcode": "passcode_value"})
        self.assertEqual(config.bran, "bran_value")

    def test_bran_property_setter(self):
        """Test bran property setter"""
        config = SentinelConfig()
        config.bran = "9876543210987654321098"
        self.assertEqual(config.bran, "9876543210987654321098")
        self.assertIn("bran", config._data)

    def test_bran_property_setter_removes_passcode(self):
        """Test bran property setter removes 'passcode' key if it exists"""
        config = SentinelConfig({"passcode": "old_passcode"})
        config.bran = "new_bran"
        self.assertEqual(config.bran, "new_bran")
        self.assertNotIn("passcode", config._data)
        self.assertIn("bran", config._data)

    def test_bran_property_setter_none(self):
        """Test bran property setter with None removes both keys"""
        config = SentinelConfig({"bran": "bran_value", "passcode": "passcode_value"})
        config.bran = None
        self.assertIsNone(config.bran)
        self.assertNotIn("bran", config._data)
        self.assertNotIn("passcode", config._data)

    def test_base_property_getter_default(self):
        """Test base property returns empty string by default"""
        config = SentinelConfig()
        self.assertEqual(config.base, "")

    def test_base_property_setter(self):
        """Test base property setter"""
        config = SentinelConfig()
        config.base = "/new/base/path"
        self.assertEqual(config.base, "/new/base/path")

    def test_local_property_getter_default(self):
        """Test local property returns False by default"""
        config = SentinelConfig()
        self.assertFalse(config.local)

    def test_local_property_setter(self):
        """Test local property setter"""
        config = SentinelConfig()
        config.local = True
        self.assertTrue(config.local)

    def test_uxd_property_getter_default(self):
        """Test uxd property returns False by default"""
        config = SentinelConfig()
        self.assertFalse(config.uxd)

    def test_uxd_property_setter(self):
        """Test uxd property setter"""
        config = SentinelConfig()
        config.uxd = True
        self.assertTrue(config.uxd)

    def test_export_dir_property_getter_default(self):
        """Test export_dir property returns default path"""
        config = SentinelConfig()
        self.assertEqual(config.export_dir, "/usr/local/sentinel")

    def test_export_dir_property_setter(self):
        """Test export_dir property setter"""
        config = SentinelConfig()
        config.export_dir = "/custom/export/path"
        self.assertEqual(config.export_dir, "/custom/export/path")

    def test_registrar_property_getter(self):
        """Test registrar property returns RegistrarConfig instance"""
        config = SentinelConfig()
        self.assertIsInstance(config.registrar, RegistrarConfig)

    def test_registrar_property_setter_with_dict(self):
        """Test registrar property setter with dict"""
        config = SentinelConfig()
        config.registrar = {"aid": "ENEW123", "oobi": "http://new.com"}

        self.assertIsInstance(config.registrar, RegistrarConfig)
        self.assertEqual(config.registrar.aid, "ENEW123")
        self.assertEqual(config.registrar.oobi, "http://new.com")

    def test_registrar_property_setter_with_registrar_config(self):
        """Test registrar property setter with RegistrarConfig instance"""
        config = SentinelConfig()
        new_registrar = RegistrarConfig({"aid": "EREG456", "oobi": "http://reg.com"})
        config.registrar = new_registrar

        self.assertEqual(config.registrar.aid, "EREG456")
        self.assertEqual(config.registrar.oobi, "http://reg.com")

    def test_registrar_property_setter_with_invalid_type(self):
        """Test registrar property setter with invalid type raises TypeError"""
        config = SentinelConfig()

        with self.assertRaises(TypeError) as context:
            config.registrar = "invalid"

        self.assertIn(
            "registrar must be a dict or RegistrarConfig instance",
            str(context.exception),
        )

    def test_issuer_property_getter(self):
        """Test issuer property returns IssuerConfig instance"""
        config = SentinelConfig()
        self.assertIsInstance(config.issuer, IssuerConfig)

    def test_issuer_property_setter_with_dict(self):
        """Test issuer property setter with dict"""
        config = SentinelConfig()
        config.issuer = {"aid": "EISS789", "oobi": "http://issuer.com"}

        self.assertIsInstance(config.issuer, IssuerConfig)
        self.assertEqual(config.issuer.aid, "EISS789")
        self.assertEqual(config.issuer.oobi, "http://issuer.com")

    def test_issuer_property_setter_with_issuer_config(self):
        """Test issuer property setter with IssuerConfig instance"""
        config = SentinelConfig()
        new_issuer = IssuerConfig({"aid": "EISS123", "oobi": "http://iss.com"})
        config.issuer = new_issuer

        self.assertEqual(config.issuer.aid, "EISS123")
        self.assertEqual(config.issuer.oobi, "http://iss.com")

    def test_issuer_property_setter_with_invalid_type(self):
        """Test issuer property setter with invalid type raises TypeError"""
        config = SentinelConfig()

        with self.assertRaises(TypeError) as context:
            config.issuer = 123

        self.assertIn(
            "issuer must be a dict or IssuerConfig instance", str(context.exception)
        )

    def test_save_syncs_nested_configs(self):
        """Test save syncs registrar and issuer configs to internal data"""
        config_file = Path(self.temp_dir) / "sync_test.yaml"

        config = SentinelConfig()
        config.registrar.aid = "ESYNC123"
        config.issuer.aid = "EISSSYNC456"
        config.name = "sync-db"

        config.save(str(config_file))

        # Reload and verify nested configs were saved
        with open(config_file, "r") as f:
            saved_data = yaml.safe_load(f)

        self.assertEqual(saved_data["registrar"]["aid"], "ESYNC123")
        self.assertEqual(saved_data["issuer"]["aid"], "EISSSYNC456")
        self.assertEqual(saved_data["name"], "sync-db")

    def test_yaml_formatting_preferences(self):
        """Test that saved YAML uses correct formatting (no flow style, unsorted keys)"""
        config_file = Path(self.temp_dir) / "format_test.yaml"

        config = SentinelConfig()
        config.name = "format-test"
        config.alias = "test-alias"
        config.registrar.aid = "EFORMAT123"
        config.registrar.oobi = "http://format.test"
        config.issuer.aid = "EISSFORMAT456"
        config.issuer.oobi = "http://issuer.format.test"

        config.save(str(config_file))

        # Read raw file content
        with open(config_file, "r") as f:
            content = f.read()

        # Verify proper indentation for nested structures
        self.assertIn("registrar:", content)
        self.assertIn("  aid:", content)
        self.assertIn("issuer:", content)

        # Verify multiline format (not flow style like {aid: ..., oobi: ...})
        lines = content.split("\n")
        registrar_line_idx = next(
            i for i, line in enumerate(lines) if "registrar:" in line
        )
        # The line with "registrar:" should not have data on the same line
        self.assertEqual(lines[registrar_line_idx].strip(), "registrar:")

    def test_config_path_is_stored(self):
        """Test that config path is stored when loading from file"""
        config_file = Path(self.temp_dir) / "path_test.yaml"

        with open(config_file, "w") as f:
            yaml.safe_dump({"name": "test"}, f)

        config = SentinelConfig.load(str(config_file))

        self.assertEqual(config._config_path, str(config_file))


if __name__ == "__main__":
    unittest.main()
