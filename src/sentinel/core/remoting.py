# -*- coding: utf-8 -*-
"""
sentinel.core.remoting module

"""
import json
from mailbox import Message
from typing import Any

from kept.hk.essring import APIClient
from keri import help
from keri.app.habbing import Habery
from requests_toolbelt import MultipartDecoder

logger = help.ogler.getLogger()


async def sync_watched_identifier(
        hby: Habery,
        essr: "APIClient",
        aid: str
) -> dict[str, Any]:
    """
    Trigger a resync for a connection in healthKERI.

    Args:
        hby: Habery instance
        essr: ESSR API client instance
        aid: AID of the connection to resync

    Returns:
        Dict with {'success': True} or {'success': False, 'error': str}
    """
    try:
        response = await essr.request(
            path=f"/watched/{aid}",
            method="GET",
            timeout=30
        )

        if response and response.status_code in (200, 202):
            data = ims = None
            decoder = MultipartDecoder.from_response(response)
            for part in decoder.parts:
                msg = Message()
                msg['content-type'] = part.headers[b'content-disposition'].decode("utf-8")
                params = dict(msg.get_params() or {})

                if params["name"] == "doc":
                    # We are expecting a CESR stream of an inception event
                    data = json.loads(part.content.decode("utf-8"))

                elif params["name"] == "cesr":
                    # We are expecting a CESR stream of a KEL event
                    ims = part.content

            if data is None or ims is None:
                print(f"Failed to parse response: {response.text}")
                return {'success': False, 'error': "Invalid response from connection service"}

            hby.psr.parse(ims)
            hby.kvy.processEscrows()
            hby.rvy.processEscrowReply()

            return {'success': True, 'data': data}
        else:
            try:
                error_data = response.json() if response else {}
                error_msg = error_data.get('description', f"Status {response.status_code if response else 'N/A'}")
            except:
                error_msg = f"Status {response.status_code if response else 'N/A'}"

            logger.error(f"Failed to resync connection: {error_msg}")
            return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.exception(f"Error resyncing connection: {e}")
        return {'success': False, 'error': str(e)}

