# -*- encoding: utf-8 -*-
"""
sentinel.core.authing module

"""
import typing
from urllib.parse import urlparse, urlsplit

from httpx import Auth, Request, Response
from keri import kering
from keri.app.habbing import Hab
from keri.core.eventing import Kever
from keri.end import ending
from keri.help import helping


class Authenticater:
    DefaultFields = ["@method",
                     "@path",
                     "Content-Length",
                     "Signify-Resource",
                     "Signify-Timestamp"]

    def __init__(self, hab: Hab, agent: typing.Optional[Kever]):
        """ Create Agent Authenticator for verifying requests and signing responses

        Parameters:
            hab(Hab): habitat of Agent for signing responses
            agent(Optional[Kever]): agent identifier for verifying responses

        Returns:
              Authenicator:  the configured habery

        """
        self.hab = hab
        self.agent = agent

    def verify(self, rep):
        url = urlparse(rep.request.url)
        if "SIGNIFY-RESOURCE" not in rep.headers:
            raise kering.AuthNError("No valid signature from agent on response.")

        resource = rep.headers["SIGNIFY-RESOURCE"]
        if resource != self.agent.serder.pre or not self.verifysig(rep.headers, rep.request.method, url.path):
            raise kering.AuthNError("No valid signature from agent on response.")

    def verifysig(self, headers, method, path):
        headers = headers
        if "SIGNATURE-INPUT" not in headers:
            return False

        siginput = headers["SIGNATURE-INPUT"]

        if "SIGNATURE" not in headers:
            return False

        signature = headers["SIGNATURE"]

        inputs = ending.desiginput(siginput.encode("utf-8"))
        inputs = [i for i in inputs if i.name == "signify"]

        if not inputs:
            return False

        for inputage in inputs:
            items = []
            for field in inputage.fields:
                if field.startswith("@"):
                    if field == "@method":
                        items.append(f'"{field}": {method}')
                    elif field == "@path":
                        items.append(f'"{field}": {path}')

                else:
                    key = field.upper()
                    field = field.lower()
                    if key not in headers:
                        continue

                    value = ending.normalize(headers[key])
                    items.append(f'"{field}": {value}')

            values = [f"({' '.join(inputage.fields)})", f"created={inputage.created}"]
            if inputage.expires is not None:
                values.append(f"expires={inputage.expires}")
            if inputage.nonce is not None:
                values.append(f"nonce={inputage.nonce}")
            if inputage.keyid is not None:
                values.append(f"keyid={inputage.keyid}")
            if inputage.context is not None:
                values.append(f"context={inputage.context}")
            if inputage.alg is not None:
                values.append(f"alg={inputage.alg}")

            params = ';'.join(values)

            items.append(f'"@signature-params: {params}"')
            ser = "\n".join(items).encode("utf-8")

            signages = ending.designature(signature)
            cig = signages[0].markers[inputage.name]
            if not self.agent.verfers[0].verify(sig=cig.raw, ser=ser):
                raise kering.AuthNError(f"Signature for {inputage} invalid")

        return True

    def sign(self, headers, method, path, fields=None):
        """ Generate and add Signature Input and Signature fields to headers

        Parameters:
            headers (dict): HTTP header to sign
            method (str): HTTP method name of request/response
            path (str): HTTP Query path of request/response
            fields (Optional[list]): Optional list of Signature Input fields to sign.

        Returns:
            headers (dict): Modified headers with new Signature and Signature Input fields

        """

        if fields is None:
            fields = self.DefaultFields

        header, qsig = ending.siginput("signify", method, path, headers, fields=fields, hab=self.hab,
                                       alg="ed25519", keyid=self.hab.pre)
        for key, val in header.items():
            headers[key] = val

        signage = ending.Signage(markers=dict(signify=qsig), indexed=False, signer=None, ordinal=None, digest=None,
                                 kind=None)
        for key, val in ending.signature([signage]).items():
            headers[key] = val

        return headers


class RequestAuth(Auth):

    def __init__(self, authn):
        """

        Args:
            authn(Authenticater): Provides request signing for AuthBase
        """

        self.authn = authn

    def auth_flow(self, req: Request) -> typing.Generator[Request, Response, None]:
        headers = req.headers
        headers['Signify-Resource'] = self.authn.hab.pre
        headers['Signify-Timestamp'] = helping.nowIso8601()

        if "Content-Length" not in headers and req.content:
            headers["Content-Length"] = len(req.content)

        p = urlsplit(req.url)
        path = p.path if p.path else "/"
        req.headers = self.authn.sign(headers, req.method, path)
        yield req
