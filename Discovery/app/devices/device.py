"""Base device data model."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Device:
    ip: str
    mac: str = ""
    hostname: str = ""
    vendor: str = ""
    model: str = ""
    os_type: str = "unknown"    # mikrotik | ubiquiti | unknown
    status: str = "online"
    ssh_open: bool = False
    api_open: bool = False
    uptime: str = ""
    firmware: str = ""
    last_seen: str = ""
    first_seen: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Device":
        return cls(
            ip=data.get("ip", ""),
            mac=data.get("mac", ""),
            hostname=data.get("hostname", ""),
            vendor=data.get("vendor", ""),
            model=data.get("model", ""),
            os_type=data.get("os_type", "unknown"),
            status=data.get("status", "online"),
            ssh_open=bool(data.get("ssh_open", False)),
            api_open=bool(data.get("api_open", False)),
            uptime=data.get("uptime", ""),
            firmware=data.get("firmware", ""),
            last_seen=data.get("last_seen", ""),
            first_seen=data.get("first_seen", ""),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "model": self.model,
            "os_type": self.os_type,
            "status": self.status,
            "ssh_open": int(self.ssh_open),
            "api_open": int(self.api_open),
            "uptime": self.uptime,
            "firmware": self.firmware,
            "last_seen": self.last_seen,
            "first_seen": self.first_seen,
            "notes": self.notes,
        }

    @property
    def is_mikrotik(self) -> bool:
        return self.os_type == "mikrotik"

    @property
    def is_ubiquiti(self) -> bool:
        return self.os_type == "ubiquiti"

    @property
    def display_name(self) -> str:
        return self.hostname or self.model or self.ip
