"""MikroTik Neighbor Discovery Protocol (MNDP) scanner."""

import socket
import struct
import threading
import time


MNDP_PORT = 5678
MNDP_TIMEOUT = 3.0
BROADCAST = "255.255.255.255"

# TLV type codes
TLV_MAC        = 0x0001
TLV_IDENTITY   = 0x0005
TLV_VERSION    = 0x0007
TLV_PLATFORM   = 0x0008
TLV_UPTIME     = 0x000A
TLV_SOFTID     = 0x000B
TLV_BOARD      = 0x000C
TLV_IFACE      = 0x000E
TLV_IPV4       = 0x000F
TLV_IPV6       = 0x0010


def _parse_mndp_packet(data: bytes) -> dict | None:
    """Parse MNDP response TLV packet. Returns device info dict or None."""
    if len(data) < 4:
        return None

    # Skip 4-byte header (type + ttl or sequence)
    offset = 4
    result: dict = {"os_type": "mikrotik"}

    while offset + 4 <= len(data):
        try:
            tlv_type, tlv_len = struct.unpack_from("!HH", data, offset)
            offset += 4
            if offset + tlv_len > len(data):
                break
            value = data[offset: offset + tlv_len]
            offset += tlv_len

            if tlv_type == TLV_MAC and tlv_len == 6:
                result["mac"] = ":".join(f"{b:02X}" for b in value)
            elif tlv_type == TLV_IDENTITY:
                result["identity"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_VERSION:
                result["firmware"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_PLATFORM:
                result["platform"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_UPTIME and tlv_len == 4:
                secs = struct.unpack_from("!I", value)[0]
                result["uptime"] = _format_uptime(secs)
            elif tlv_type == TLV_BOARD:
                result["model"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_IFACE:
                result["interface"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_IPV4 and tlv_len >= 4:
                result["ip_mndp"] = socket.inet_ntoa(value[:4])
        except Exception:
            break

    return result if len(result) > 1 else None


def _format_uptime(seconds: int) -> str:
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}:{mins:02d}:{secs:02d}"
    return f"{hours:02d}:{mins:02d}:{secs:02d}"


def scan_mndp(timeout: float = MNDP_TIMEOUT) -> list[dict]:
    """
    Broadcast MNDP discovery packet and collect MikroTik responses.
    Returns list of device info dicts.
    """
    devices: dict[str, dict] = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        sock.bind(("", 0))

        # MNDP discovery request: 4 zero bytes
        request = b"\x00\x00\x00\x00"
        sock.sendto(request, (BROADCAST, MNDP_PORT))

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                src_ip = addr[0]
                info = _parse_mndp_packet(data)
                if info and src_ip not in devices:
                    info["ip"] = src_ip
                    if "identity" in info:
                        info["hostname"] = info.pop("identity")
                    devices[src_ip] = info
            except socket.timeout:
                continue
            except Exception:
                break
    except Exception:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass

    return list(devices.values())
