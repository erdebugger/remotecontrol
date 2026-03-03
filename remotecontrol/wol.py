from __future__ import annotations

import socket


def send_magic_packet(mac: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> None:
    mac_clean = mac.replace(":", "").replace("-", "").strip()
    if len(mac_clean) != 12:
        raise ValueError("MAC inválida")

    payload = bytes.fromhex("FF" * 6 + mac_clean * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(payload, (broadcast_ip, port))
