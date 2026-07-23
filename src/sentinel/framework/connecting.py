import json
import os
import stat
from os import mkdir
from os.path import exists
from pathlib import Path

import pyotp
import requests
from kept.hk.configing import HealthKERIConfig
from kept.hk.essring import APIClient
from keri import kering
from keri.app.habbing import Hab, Habery
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import coring
from keri.help import helping
from keri.kering import ConfigurationError

from sentinel.core.oobiing import load_oobi
from sentinel.core.querying import Receiptor


async def connect_to_healthkeri(
    server_name,
    sentinel_hby,
    sentinel_hab,
    auth_key,
    server_hby=None,
    server_hab=None,
    witness=False,
):
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

    if response.status_code != 201:
        raise ValueError(f"Error registering server with healthKERI: {response.text}")

    if server_hab and witness:
        config = HealthKERIConfig.get_instance()
        essr = APIClient(
            url=config.protected_url,
            root=config.api_aid,
            hby=sentinel_hby,
            hab=sentinel_hab,
        )
        print("Reserving witness for server...")
        witness = await reserve_witness_for_server(essr, server_name, server_hab)
        witness_aid = witness.get("eid", "")
        witness_name = witness.get("name", "")
        witness_oobi = witness.get("oobi", "")
        print(f"Witness {witness_name} ({witness_aid}) reserved.")
        load_oobi(server_hby, witness_oobi, witness_name)
        print("Oobi loaded for witness, now authenticating...")
        otp = authenticate_witness(server_hab, witness_aid)

        print("Witness authenticated, now rotating...")
        await rotate_witness(server_hby, server_hab, witness_aid, otp)
        print("Witness rotation complete.")


async def reserve_witness_for_server(essr, server_name, server_hab):
    """Reserve a witness for the server in healthKERI.

    This method reserves a witness node for the server's identifier in the
    healthKERI network, enabling the server to participate in the KERI protocol
    with witness support.

    Args:
        essr (APIClient): The authenticated API client instance for making requests
            to the healthKERI protected endpoints.
        server_hab (Habitat): The server's habitat for which a witness should be
            reserved.

    Returns:
        dict[str, Any]: A dictionary containing the witness's name and OOBIs.

    Raises:
        ValueError: If witness reservation fails or no witnesses are available.
        ConfigurationError: If the witness configuration is invalid.

    """
    try:
        # Build list of witness docs
        docs = [
            {"cid": server_hab.pre, "name": f"{server_name}-{server_hab.name}-wit-0"}
        ]

        # Make POST request to create witnesses
        response = await essr.request(
            path="/witnesses", method="POST", json=docs, timeout=30  # type: ignore
        )
        if response and response.status_code == 201:
            witnesses = response.json()
            return witnesses[0]
        else:
            if response:
                print(
                    f"Failed to provision witnesses. Status: {response.status_code} - {response.text}"
                )
                try:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "description", f"Status {response.status_code}"
                    )
                    raise ValueError(error_msg)
                except Exception:
                    raise
            else:
                print("Failed to provision witnesses: No response")
                raise ValueError("No response from server")

    except Exception as e:
        raise e


def authenticate_witness(server_hab, witness):
    """Authenticate the server with its assigned witness.

    This method completes the witness authentication process by establishing a
    secure connection between the server's identifier and its assigned witness
    node in the KERI network.

    Args:
        server_hab (Habitat): The server's habitat that needs to authenticate
            with its witness.
        witness (str): The AID of the witness node to authenticate with.

    Returns:
        None

    Raises:
        ValueError: If authentication with the witness fails.
        ConnectionError: If unable to connect to the witness node.
        ConfigurationError: If witness information is missing or invalid.

    """
    body = bytearray()
    for msg in server_hab.db.clonePreIter(pre=server_hab.pre):
        body.extend(msg)

    files = dict([("kel", body.decode("utf-8"))])

    headers = dict([(CESR_DESTINATION_HEADER, witness)])

    urls = server_hab.fetchUrls(
        eid=witness, scheme=kering.Schemes.http
    ) or server_hab.fetchUrls(eid=witness, scheme=kering.Schemes.https)
    if not urls:
        raise kering.MissingEntryError(
            f"unable to query witness {witness}, no http endpoint"
        )

    url = (
        urls[kering.Schemes.http]
        if kering.Schemes.http in urls
        else urls[kering.Schemes.https]
    )

    rep = requests.post(f"{url.rstrip('/')}/aids", headers=headers, files=files)

    if rep.status_code == 200:
        data = rep.json()

        totp = data["totp"]
        m = coring.Matter(qb64=totp)  # refactor this to use cipher
        d = coring.Matter(qb64=server_hab.decrypt(ser=m.raw))
        otp = pyotp.TOTP(s=d.raw.decode("utf-8"))

        codes = dict()

        if not exists(Path.home() / ".keriguard"):
            mkdir(Path.home() / ".keriguard")

        path = Path.home() / ".keriguard" / server_hab.pre

        try:
            with open(path, "r") as f:
                lines = f.readlines()
                for line in lines:
                    splits = line.split(":")
                    if len(splits) != 2:
                        continue
                    aid, code = splits
                    codes[aid] = code
        except OSError:
            pass

        codes[witness] = otp.secret
        with open(path, "w") as f:
            for aid, code in codes.items():
                print(f"{aid}:{code.rstrip()}", file=f)

        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return otp

    else:
        raise ValueError(rep.text)


async def rotate_witness(server_hby: Habery, server_hab: Hab, witness_aid, otp):
    """Rotate the server's identifier with the witness using OTP authentication.

    This method performs a key rotation for the server's identifier with its
    assigned witness node, using the provided one-time password for authentication.

    Args:
        server_hby (Habery): The server's database environment.
        server_hab (Habitat): The server's habitat that needs to perform the rotation.
        witness_aid (str): The AID of the witness node to rotate with.
        otp: The one-time password object for witness authentication.

    Returns:
        None

    Raises:
        ValueError: If the rotation fails or witness does not accept the OTP.
        ConnectionError: If unable to connect to the witness node.
        ConfigurationError: If rotation parameters are invalid.

    """
    server_hab.rotate(isith="1", ncount=1, nsith="1", toad=1, adds=[witness_aid])

    time = helping.nowIso8601()
    auths = {witness_aid: f"{otp.at(helping.fromIso8601(time))}#{time}"}

    receiptor = Receiptor(hby=server_hby)
    await receiptor.receipt(server_hab.pre, sn=server_hab.kever.sn, auths=auths)
