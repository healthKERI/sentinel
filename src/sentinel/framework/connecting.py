import json

import requests
from kept.hk.configing import HealthKERIConfig
from keri import kering
from keri.kering import ConfigurationError


def connect_to_healthkeri(server_name, sentinel_hab, auth_key, server_hab=None):
    config = HealthKERIConfig.get_instance()

    response = requests.get(config.root_oobi)
    sentinel_hab.psr.parse(ims=response.content)
    response = requests.get(config.api_oobi)
    sentinel_hab.psr.parse(ims=response.content)

    sentinel_hab.kvy.processEscrows()

    if (
        config.root_aid not in sentinel_hab.kevers
        or config.api_aid not in sentinel_hab.kevers
    ):
        raise ConfigurationError(
            "Unable to resolve healthKERI root identifiers. Please check your configuration"
        )

    # "aid", "name", "server_auth_code"
    data = dict(name=server_name, aid=sentinel_hab.pre, server_auth_code=auth_key)

    if server_hab:
        data["server_aid"] = server_hab.pre

    sentinel_kel = sentinel_hab.replyToOobi(
        sentinel_hab.pre, role=kering.Roles.controller
    )
    files = {
        "kel": ("output.bin", bytes(sentinel_kel), "application/octet-stream"),
        "doc": ("data.json", json.dumps(data), "application/json"),
    }

    if server_hab:
        server_kel = server_hab.replyToOobi(
            server_hab.pre, role=kering.Roles.controller
        )
        files["server_kel"] = (
            "server_hab.bin",
            bytes(server_kel),
            "application/octet-stream",
        )

    response = requests.post(
        f"{config.unprotected_url}/account/teams/servers", files=files
    )

    if response.status_code != 201:  # type: ignore
        raise ValueError(f"Error registering server with healthKERI: {response.text}")

    data = response.json()
    return data
