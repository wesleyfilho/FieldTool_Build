"""Ubiquiti Device Discovery Protocol scanner."""

import socket
import struct
import time


UBNT_PORT = 10001
UBNT_TIMEOUT = 3.0
BROADCAST = "255.255.255.255"

# Discovery request packet
UBNT_REQUEST = bytes([0x01, 0x00, 0x00, 0x00])

# TLV type codes
TLV_HWADDR      = 0x01
TLV_IPINFO      = 0x02
TLV_FIRMWARE    = 0x03
TLV_UPTIME      = 0x0A
TLV_HOSTNAME    = 0x0B
TLV_MODEL       = 0x0C
TLV_ESSID       = 0x0D
TLV_MODEL_SHORT = 0x15
TLV_PLATFORM    = 0x16


def _parse_ubnt_packet(data: bytes) -> dict | None:
    """Parse UBNT discovery response. Returns device info or None."""
    if len(data) < 4:
        return None

    # Header: version(1) + cmd(1) + length(2)
    version = data[0]
    cmd = data[1]
    if cmd not in (0x00, 0x06):  # discovery response commands
        pass  # still try to parse

    offset = 4
    result: dict = {"os_type": "ubiquiti"}

    while offset + 3 <= len(data):
        try:
            tlv_type = data[offset]
            tlv_len = struct.unpack_from("!H", data, offset + 1)[0]
            offset += 3
            if offset + tlv_len > len(data):
                break
            value = data[offset: offset + tlv_len]
            offset += tlv_len

            if tlv_type == TLV_HWADDR and tlv_len == 6:
                result["mac"] = ":".join(f"{b:02X}" for b in value)
            elif tlv_type == TLV_IPINFO and tlv_len >= 10:
                # 6 bytes MAC + 4 bytes IP
                ip_bytes = value[6:10]
                result["ip_ubnt"] = socket.inet_ntoa(ip_bytes)
            elif tlv_type == TLV_FIRMWARE:
                result["firmware"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_UPTIME and tlv_len == 4:
                secs = struct.unpack_from("!I", value)[0]
                result["uptime"] = _format_uptime(secs)
            elif tlv_type == TLV_HOSTNAME:
                result["hostname"] = value.decode("utf-8", errors="replace")
            elif tlv_type in (TLV_MODEL, TLV_MODEL_SHORT):
                result["model"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_ESSID:
                result["essid"] = value.decode("utf-8", errors="replace")
            elif tlv_type == TLV_PLATFORM:
                result["platform"] = value.decode("utf-8", errors="replace")
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


def scan_ubnt(timeout: float = UBNT_TIMEOUT) -> list[dict]:
    """
    Broadcast Ubiquiti discovery packet and collect responses.
    Returns list of device info dicts.
    """
    devices: dict[str, dict] = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        sock.bind(("", 0))

        sock.sendto(UBNT_REQUEST, (BROADCAST, UBNT_PORT))

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                src_ip = addr[0]
                info = _parse_ubnt_packet(data)
                if info and src_ip not in devices:
                    info["ip"] = src_ip
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
