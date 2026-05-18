from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeEnvironmentProbe:
    def local_ip_addresses(self) -> set[str]:
        addresses = {"127.0.0.1", "::1"}
        try:
            hostname = socket.gethostname()
            for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
                if family in {socket.AF_INET, socket.AF_INET6}:
                    addresses.add(str(sockaddr[0]))
        except OSError:
            pass
        return addresses

    def is_port_available(self, ip_address: str, port: int) -> bool:
        host = ip_address.split("/", 1)[0]
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                return False
        return True
