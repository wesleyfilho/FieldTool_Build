"""MikroTik device configuration via RouterOS API and SSH."""

import socket
from app.database import db
from app.core.security import decrypt_credentials

DEFAULT_CREDENTIALS = [
    ("admin", ""),
    ("admin", "admin"),
    ("admin", "mikrotik"),
]


class MikroTikConfig:
    def __init__(self, ip: str, username: str = "admin", password: str = "", port: int = 8728):
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self._api = None

    def connect(self) -> bool:
        """Connect via RouterOS API."""
        try:
            import librouteros
            self._api = librouteros.connect(
                host=self.ip,
                username=self.username,
                password=self.password,
                port=self.port,
                timeout=5,
            )
            db.add_log("INFO", "CONFIG", f"Conectado ao MikroTik {self.ip}", self.ip)
            return True
        except Exception as e:
            db.add_log("ERROR", "CONFIG", f"Falha ao conectar MikroTik {self.ip}: {e}", self.ip)
            return False

    def connect_by_mac(self, mac: str) -> bool:
        """Resolve MAC to IP via local ARP table, then connect. For directly-cabled devices."""
        from app.network.arp_scan import find_ip_by_mac
        ip = find_ip_by_mac(mac)
        if not ip:
            db.add_log("WARNING", "CONFIG", f"MAC {mac} nao encontrado na tabela ARP — execute um scan primeiro")
            return False
        self.ip = ip
        db.add_log("INFO", "CONFIG", f"MAC {mac} resolvido para {ip}", ip)
        return self.connect()

    def disconnect(self):
        if self._api:
            try:
                self._api.close()
            except Exception:
                pass
            self._api = None

    def auto_login(self) -> tuple[bool, str, str]:
        """Try default credentials. Returns (success, username, password)."""
        saved = db.get_credential(self.ip, proto="api")
        if saved:
            try:
                u, p = decrypt_credentials(saved["username_enc"], saved["password_enc"])
                self.username, self.password = u, p
                if self.connect():
                    return True, u, p
            except Exception:
                pass

        for user, passwd in DEFAULT_CREDENTIALS:
            self.username, self.password = user, passwd
            if self.connect():
                return True, user, passwd
        return False, "", ""

    def get_identity(self) -> str:
        if not self._api:
            return ""
        try:
            result = list(self._api("/system/identity/print"))
            return result[0].get("name", "") if result else ""
        except Exception:
            return ""

    def get_resource(self) -> dict:
        if not self._api:
            return {}
        try:
            result = list(self._api("/system/resource/print"))
            return dict(result[0]) if result else {}
        except Exception:
            return {}

    def get_interfaces(self) -> list[dict]:
        if not self._api:
            return []
        try:
            return [dict(r) for r in self._api("/interface/print")]
        except Exception:
            return []

    def get_ip_addresses(self) -> list[dict]:
        if not self._api:
            return []
        try:
            return [dict(r) for r in self._api("/ip/address/print")]
        except Exception:
            return []

    # ---- Configuration methods ----

    def set_identity(self, name: str) -> bool:
        return self._run_cmd("/system/identity/set", name=name)

    def set_ip(self, interface: str, address: str, network: str = "") -> bool:
        # Remove existing address on interface
        try:
            existing = list(self._api("/ip/address/print", **{"?interface": interface}))
            for e in existing:
                self._api("/ip/address/remove", **{".id": e[".id"]})
        except Exception:
            pass
        return self._run_cmd("/ip/address/add", address=address, interface=interface)

    def set_dhcp_client(self, interface: str) -> bool:
        return self._run_cmd("/ip/dhcp-client/add", interface=interface, **{"add-default-route": "yes"})

    def set_dhcp_server(self, interface: str, pool_range: str,
                        gateway: str, dns: str = "8.8.8.8") -> bool:
        ok = True
        ok &= self._run_cmd("/ip/pool/add", name="dhcp_pool", ranges=pool_range)
        ok &= self._run_cmd("/ip/dhcp-server/network/add",
                            address=pool_range.split("-")[0] + "/24",
                            gateway=gateway, **{"dns-server": dns})
        ok &= self._run_cmd("/ip/dhcp-server/add",
                            name="dhcp1", interface=interface,
                            **{"address-pool": "dhcp_pool", "disabled": "no"})
        return ok

    def set_nat_masquerade(self, out_interface: str) -> bool:
        return self._run_cmd(
            "/ip/firewall/nat/add",
            chain="srcnat",
            action="masquerade",
            **{"out-interface": out_interface}
        )

    def set_wireless(self, interface: str, ssid: str, password: str,
                     band: str = "2ghz-b/g/n", mode: str = "ap-bridge") -> bool:
        ok = self._run_cmd(
            "/interface/wireless/set",
            **{".id": interface, "ssid": ssid, "band": band, "mode": mode}
        )
        ok &= self._run_cmd(
            "/interface/wireless/security-profiles/set",
            **{".id": "default", "authentication-types": "wpa2-psk",
               "wpa2-pre-shared-key": password, "mode": "dynamic-keys"}
        )
        return ok

    def apply_template(self, template: dict) -> tuple[bool, list[str]]:
        """Apply a MikroTik configuration template. Returns (success, messages)."""
        if not self._api:
            return False, ["Nao conectado"]

        messages: list[str] = []
        success = True

        try:
            config_type = template.get("config_type", "")
            params = template.get("params", {})

            if config_type == "ap":
                ok = self.set_wireless(
                    interface=params.get("wlan_iface", "wlan1"),
                    ssid=params.get("ssid", "MikroTik"),
                    password=params.get("password", ""),
                    band=params.get("band", "2ghz-b/g/n"),
                    mode="ap-bridge",
                )
                messages.append(f"Wireless AP: {'OK' if ok else 'ERRO'}")
                success &= ok

                if params.get("ip"):
                    ok = self.set_ip(params.get("lan_iface", "ether1"), params["ip"])
                    messages.append(f"IP LAN: {'OK' if ok else 'ERRO'}")
                    success &= ok

                if params.get("dhcp_pool"):
                    ok = self.set_dhcp_server(
                        params.get("lan_iface", "ether1"),
                        params["dhcp_pool"],
                        params.get("gateway", "192.168.88.1"),
                        params.get("dns", "8.8.8.8"),
                    )
                    messages.append(f"DHCP Server: {'OK' if ok else 'ERRO'}")
                    success &= ok

                if params.get("nat"):
                    ok = self.set_nat_masquerade(params.get("wan_iface", "ether1"))
                    messages.append(f"NAT Masquerade: {'OK' if ok else 'ERRO'}")
                    success &= ok

            elif config_type == "client":
                ok = self.set_wireless(
                    interface=params.get("wlan_iface", "wlan1"),
                    ssid=params.get("ssid", ""),
                    password=params.get("password", ""),
                    mode="station",
                )
                messages.append(f"Wireless Cliente: {'OK' if ok else 'ERRO'}")
                success &= ok

            if not messages:
                messages.append("Template aplicado")

        except Exception as e:
            success = False
            messages.append(f"Erro: {e}")

        db.add_log(
            "SUCCESS" if success else "ERROR", "CONFIG",
            f"Template MikroTik {template.get('name','')}: {'; '.join(messages)}",
            self.ip
        )
        return success, messages

    def _run_cmd(self, path: str, **kwargs) -> bool:
        try:
            list(self._api(path, **kwargs))
            return True
        except Exception as e:
            db.add_log("ERROR", "CONFIG", f"MikroTik cmd {path}: {e}", self.ip)
            return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()
