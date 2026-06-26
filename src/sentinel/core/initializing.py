# -*- encoding: utf-8 -*-
"""
sentinel.core.initializing module

Methods for initializing a Sentinel instance

"""

from pathlib import Path
from typing import Optional, Dict, Any, Union

import yaml


class RegistrarConfig:
    """Configuration for the registrar."""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = data or dict()

    @property
    def aid(self) -> str:
        """The registrar's AID."""
        return self._data.get("aid", "")

    @aid.setter
    def aid(self, value: str) -> None:
        """Set the registrar's AID."""
        self._data["aid"] = value

    @property
    def oobi(self) -> str:
        """The registrar's OOBI URL."""
        return self._data.get("oobi", "")

    @oobi.setter
    def oobi(self, value: str) -> None:
        """Set the registrar's OOBI URL."""
        self._data["oobi"] = value

    @property
    def url(self) -> Optional[str]:
        """The registrar's API endpoint URL."""
        return self._data.get("url")

    @url.setter
    def url(self, value: Optional[str]) -> None:
        """Set the registrar's API endpoint URL."""
        if value is None:
            self._data.pop("url", None)
        else:
            self._data["url"] = value

    @property
    def ipaddress(self) -> Optional[str]:
        """The registrar's internal Wireguard address."""
        return self._data.get("ipaddress")

    @ipaddress.setter
    def ipaddress(self, value: Optional[str]) -> None:
        """Set the registrar's internal Wireguard address."""
        if value is None:
            self._data.pop("ipaddress", None)
        else:
            self._data["ipaddress"] = value

    @property
    def endpoint(self) -> Optional[str]:
        """The registrar's Wireguard address and port."""
        return self._data.get("endpoint")

    @endpoint.setter
    def endpoint(self, value: Optional[str]) -> None:
        """Set the registrar's Wireguard address and port."""
        if value is None:
            self._data.pop("endpoint", None)
        else:
            self._data["endpoint"] = value


class IssuerConfig:
    """Configuration for the issuer."""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        self._data = data or dict()

    @property
    def aid(self) -> str:
        """The issuer's AID."""
        return self._data.get("aid", "")

    @aid.setter
    def aid(self, value: str) -> None:
        """Set the issuer's AID."""
        self._data["aid"] = value

    @property
    def oobi(self) -> str:
        """The issuer's OOBI URL."""
        return self._data.get("oobi", "")

    @oobi.setter
    def oobi(self, value: str) -> None:
        """Set the issuer's OOBI URL."""
        self._data["oobi"] = value


class SentinelConfig:
    """
    Configuration loader and accessor for Sentinel initialization.

    This class reads a YAML configuration file and provides typed access
    to all configuration values needed for initializing a Sentinel instance.
    All properties support both getting and setting values.

    Example:
        # Load configuration
        config = SentinelConfig.load("/path/to/sentinel.conf")
        print(config.registrar.aid)
        print(config.registrar.sentinel.oobi)
        print(config.issuer.aid)

        # Modify configuration values
        config.name = "new-db-name"
        config.alias = "new-alias"
        config.loglevel = "DEBUG"
        config.registrar.aid = "NEW_AID"

        # Set nested configurations
        config.registrar = {"aid": "REG123", "oobi": "http://example.com"}
        config.issuer = {"aid": "ISS456", "oobi": "http://issuer.com"}

        # Save configuration back to the same file
        config.save()

        # Save to a different file
        config.save("/path/to/new-sentinel.conf")
    """

    def __init__(
        self, data: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None
    ):
        self._data = data or dict()
        if self._data:
            self._registrar = RegistrarConfig(data.get("registrar", {}))
            self._issuer = IssuerConfig(data.get("issuer", {}))
        else:
            self._registrar = RegistrarConfig()
            self._issuer = IssuerConfig()

        self._config_path = config_path

    @classmethod
    def load(cls, config_path: str) -> "SentinelConfig":
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            SentinelConfig instance with loaded configuration

        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the YAML is malformed
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        return cls(data, config_path=str(path))

    def save(self, config_path: Optional[str] = None) -> None:
        """
        Save configuration to a YAML file.

        Args:
            config_path: Path to save the YAML configuration file.
                        If not provided, saves to the path from which the config was loaded.

        Raises:
            ValueError: If no config_path provided and config wasn't loaded from a file
            OSError: If unable to write to the specified path
        """
        # Determine which path to use
        save_path = config_path if config_path is not None else self._config_path

        if save_path is None:
            raise ValueError(
                "No config path specified. Provide a path or load config from a file first."
            )

        path = Path(save_path)

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        if self._registrar:
            self._data["registrar"] = self._registrar._data

        if self._issuer:
            self._data["issuer"] = self._issuer._data

        # Write the configuration to YAML file
        with open(path, "w") as f:
            yaml.safe_dump(
                self._data,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                indent=2,
            )

    @property
    def registrar(self) -> RegistrarConfig:
        """The registrar configuration."""
        return self._registrar

    @registrar.setter
    def registrar(self, value: Union[Dict[str, Any], "RegistrarConfig"]) -> None:
        """Set the registrar configuration."""
        if isinstance(value, RegistrarConfig):
            self._data["registrar"] = value._data
            self._registrar = value
        elif isinstance(value, dict):
            self._data["registrar"] = value
            self._registrar = RegistrarConfig(value)
        else:
            raise TypeError("registrar must be a dict or RegistrarConfig instance")

    @property
    def issuer(self) -> IssuerConfig:
        """The issuer configuration."""
        return self._issuer

    @issuer.setter
    def issuer(self, value: Union[Dict[str, Any], "IssuerConfig"]) -> None:
        """Set the issuer configuration."""
        if isinstance(value, IssuerConfig):
            self._data["issuer"] = value._data
            self._issuer = value
        elif isinstance(value, dict):
            self._data["issuer"] = value
            self._issuer = IssuerConfig(value)
        else:
            raise TypeError("issuer must be a dict or IssuerConfig instance")

    @property
    def name(self) -> Optional[str]:
        """Database environment name."""
        return self._data.get("name")

    @name.setter
    def name(self, value: Optional[str]) -> None:
        """Set the database environment name."""
        if value is None:
            self._data.pop("name", None)
        else:
            self._data["name"] = value

    @property
    def alias(self) -> Optional[str]:
        """Human readable alias for the identifier prefix."""
        return self._data.get("alias")

    @alias.setter
    def alias(self, value: Optional[str]) -> None:
        """Set the human readable alias."""
        if value is None:
            self._data.pop("alias", None)
        else:
            self._data["alias"] = value

    @property
    def server_name(self) -> Optional[str]:
        """Keriguard server keystore name (SaaS mode only)."""
        return self._data.get("server_name")

    @server_name.setter
    def server_name(self, value: Optional[str]) -> None:
        if value is None:
            self._data.pop("server_name", None)
        else:
            self._data["server_name"] = value

    @property
    def server_alias(self) -> Optional[str]:
        """Keriguard server identifier alias (SaaS mode only)."""
        return self._data.get("server_alias")

    @server_alias.setter
    def server_alias(self, value: Optional[str]) -> None:
        if value is None:
            self._data.pop("server_alias", None)
        else:
            self._data["server_alias"] = value

    @property
    def bran(self) -> Optional[str]:
        """22 character encryption passcode. Supports both 'bran' and 'passcode' keys."""
        return self._data.get("bran") or self._data.get("passcode")

    @bran.setter
    def bran(self, value: Optional[str]) -> None:
        """Set the encryption passcode (stores as 'bran' key)."""
        if value is None:
            self._data.pop("bran", None)
            self._data.pop("passcode", None)
        else:
            self._data["bran"] = value
            # Remove passcode if it exists to avoid confusion
            self._data.pop("passcode", None)

    @property
    def base(self) -> str:
        """Additional prefix to file location."""
        return self._data.get("base", "")

    @base.setter
    def base(self, value: str) -> None:
        """Set the additional prefix to file location."""
        self._data["base"] = value

    @property
    def local(self) -> bool:
        """Run local watcher services."""
        return self._data.get("local", False)

    @local.setter
    def local(self, value: bool) -> None:
        """Set whether to run local watcher services."""
        self._data["local"] = value

    @property
    def uxd(self) -> bool:
        """Listen on Unix Domain Sockets."""
        return self._data.get("uxd", False)

    @uxd.setter
    def uxd(self, value: bool) -> None:
        """Set whether to listen on Unix Domain Sockets."""
        self._data["uxd"] = value

    @property
    def export_dir(self) -> str:
        """Directory for exporting CESR files."""
        return self._data.get("export_dir", "/usr/local/sentinel")

    @export_dir.setter
    def export_dir(self, value: str) -> None:
        """Set the directory for exporting CESR files."""
        self._data["export_dir"] = value
