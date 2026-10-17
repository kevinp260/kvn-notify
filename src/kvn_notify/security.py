"""Checks on push endpoints sent by browsers.

The endpoint URL comes from the client, and the server later makes a request to
it. Without a check, a crafted subscription could make the server call internal
addresses (server-side request forgery).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeEndpoint(ValueError):
    pass


def check_push_endpoint(endpoint: str, *, resolve: bool = True) -> None:
    parts = urlsplit(endpoint)
    if parts.scheme != "https":
        raise UnsafeEndpoint("push endpoints must use https")
    host = parts.hostname
    if not host:
        raise UnsafeEndpoint("push endpoint has no host")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        if not resolve:
            return
        try:
            infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            raise UnsafeEndpoint(f"push endpoint host does not resolve: {exc}") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    for address in addresses:
        if not address.is_global:
            raise UnsafeEndpoint(f"push endpoint points to a non-public address ({address})")
