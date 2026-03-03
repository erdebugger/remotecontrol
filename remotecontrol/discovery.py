from __future__ import annotations

import ipaddress
import platform
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

from .models import Host


def _ping(ip: str, timeout_ms: int = 400) -> bool:
    is_windows = platform.system().lower().startswith("win")
    cmd = ["ping"]
    if is_windows:
        cmd += ["-n", "1", "-w", str(timeout_ms), ip]
    else:
        timeout_s = max(1, int(timeout_ms / 1000))
        cmd += ["-c", "1", "-W", str(timeout_s), ip]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode == 0


def _resolve_name(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


def discover_hosts(cidr: str, max_workers: int = 64) -> list[Host]:
    network = ipaddress.ip_network(cidr, strict=False)
    ips = [str(ip) for ip in network.hosts()]

    hosts: list[Host] = []

    def probe(ip: str) -> Host | None:
        if not _ping(ip):
            return None
        return Host(ip=ip, name=_resolve_name(ip), online=True)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for maybe_host in pool.map(probe, ips):
            if maybe_host:
                hosts.append(maybe_host)

    hosts.sort(key=lambda h: tuple(int(x) for x in h.ip.split(".")))
    return hosts
