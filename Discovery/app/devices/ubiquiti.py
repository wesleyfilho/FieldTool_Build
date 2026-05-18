"""Ubiquiti device configuration via SSH."""

import json
import time
from app.database import db
from app.core.security import decrypt_credentials

DEFAULT_CREDENTIALS = [
    ("ubnt", "ubnt"),
    ("admin", "admin"),
    ("admin", ""),
    ("ubnt", ""),
]


class UbiquitiConfig:
    def __init__(self, ip: str, username: str = "ubnt", password: str = "ubnt", port: int = 22):
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self._ssh = None

    def connect(self) -> bool:
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self.ip, port=self.port,
                username=self.username, password=self.password,
                timeout=8, banner_timeout=8, auth_timeout=8,
                look_for_keys=False, allow_agent=False,
            )
            self._ssh = client
            db.add_log("INFO", "CONFIG", f"Conectado ao Ubiquiti {self.ip}", self.ip)
            return True
        except Exception as e:
            db.add_log("ERROR", "CONFIG", f"Falha ao conectar Ubiquiti {self.ip}: {e}", self.ip)
            return False

    def disconnect(self):
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None

    def auto_login(self) -> tuple[bool, str, str]:
        saved = db.get_credential(self.ip, proto="ssh")
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

    def run_command(self, cmd: str) -> tuple[str, str]:
        """Run SSH command. Returns (stdout, stderr)."""
        if not self._ssh:
            return "", "Not connected"
        try:
            _, stdout, stderr = self._ssh.exec_command(cmd, timeout=10)
            return stdout.read().decode(), stderr.read().decode()
        except Exception as e:
            return "", str(e)

    def get_system_info(self) -> dict:
        out, _ = self.run_command("cat /proc/ubnthal/system.cfg 2>/dev/null || mca-cli-op info")
        info: dict = {}
        for line in out.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                info[k.strip()] = v.strip()
        return info

    def get_current_config(self) -> str:
        out, _ = self.run_command("cat /tmp/system.cfg")
        return out

    def apply_uci_config(self, config_lines: list[str]) -> bool:
        """Apply configuration via UCI or direct config file."""
        try:
            cfg_content = "\n".join(config_lines)
            # Write to temp file
            self._ssh_exec_series([
                f"echo '{cfg_content}' > /tmp/netdiscovery.cfg",
                "cfgmtd -w -f /tmp/netdiscovery.cfg",
                "reboot",
            ])
            return True
        except Exception as e:
            db.add_log("ERROR", "CONFIG", f"Ubiquiti apply config error: {e}", self.ip)
            return False

    def set_wireless(self, ssid: str, password: str, frequency: int = 2412,
                     channel_width: int = 20, txpower: int = 20,
                     security: str = "wpapsk", mode: str = "access-point") -> bool:
        commands = [
            f'uci set wireless.radio0.ssid="{ssid}"',
            f'uci set wireless.radio0.key="{password}"',
            f'uci set wireless.radio0.encryption="psk2"',
            f'uci set wireless.radio0.channel="{frequency}"',
            f'uci set wireless.radio0.txpower="{txpower}"',
            "uci commit wireless",
            "wifi reload",
        ]
        return self._ssh_exec_series(commands)

    def set_ip_static(self, ip: str, netmask: str, gateway: str, dns: str = "8.8.8.8") -> bool:
        commands = [
            'uci set network.lan.proto="static"',
            f'uci set network.lan.ipaddr="{ip}"',
            f'uci set network.lan.netmask="{netmask}"',
            f'uci set network.lan.gateway="{gateway}"',
            f'uci set network.lan.dns="{dns}"',
            "uci commit network",
            "/etc/init.d/network restart",
        ]
        return self._ssh_exec_series(commands)

    def apply_template(self, template: dict) -> tuple[bool, list[str]]:
        if not self._ssh:
            return False, ["Nao conectado"]

        messages: list[str] = []
        success = True
        params = template.get("params", {})
        config_type = template.get("config_type", "")

        try:
            if config_type in ("ap", "repeater"):
                ok = self.set_wireless(
                    ssid=params.get("ssid", "Ubiquiti"),
                    password=params.get("password", "ubnt1234"),
                    frequency=int(params.get("channel", 2412)),
                    txpower=int(params.get("txpower", 20)),
                )
                messages.append(f"Wireless: {'OK' if ok else 'ERRO'}")
                success &= ok

                if params.get("ip"):
                    ok = self.set_ip_static(
                        ip=params["ip"],
                        netmask=params.get("netmask", "255.255.255.0"),
                        gateway=params.get("gateway", ""),
                        dns=params.get("dns", "8.8.8.8"),
                    )
                    messages.append(f"IP Estatico: {'OK' if ok else 'ERRO'}")
                    success &= ok

            elif config_type == "client":
                commands = [
                    f'uci set wireless.radio0.mode="sta"',
                    f'uci set wireless.radio0.ssid="{params.get("ssid","")}"',
                    f'uci set wireless.radio0.key="{params.get("password","")}"',
                    "uci commit wireless",
                    "wifi reload",
                ]
                ok = self._ssh_exec_series(commands)
                messages.append(f"Modo Cliente: {'OK' if ok else 'ERRO'}")
                success &= ok

        except Exception as e:
            success = False
            messages.append(f"Erro: {e}")

        db.add_log(
            "SUCCESS" if success else "ERROR", "CONFIG",
            f"Template Ubiquiti {template.get('name','')}: {'; '.join(messages)}",
            self.ip
        )
        return success, messages

    def _ssh_exec_series(self, commands: list[str]) -> bool:
        for cmd in commands:
            out, err = self.run_command(cmd)
            if err and "error" in err.lower():
                return False
        return True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.disconnect()
