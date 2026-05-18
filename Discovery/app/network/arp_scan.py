"""ARP/Ping sweep scanner — works on Windows without Npcap."""

import subprocess
import socket
import ipaddress
import concurrent.futures
import re
import platform
from typing import Callable


def _ping(ip: str, timeout_ms: int = 500) -> bool:
    """Send single ICMP ping. Returns True if host responds."""
    try:
        if platform.system() == "Windows":
            cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]
        result = subprocess.run(cmd, capture_output=True, timeout=3)
        return result.returncode == 0
    except Exception:
        return False


def _parse_arp_table() -> dict[str, dict]:
    """Parse Windows ARP table. Returns {ip: {"mac": mac, "ip_type": "dhcp"|"static"}}."""
    ip_mac: dict[str, dict] = {}
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            # Windows format: "  192.168.1.1          aa-bb-cc-dd-ee-ff     dynamic"
            match = re.search(
                r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+"
                r"([\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2})"
                r"\s+(\w+)",
                line
            )
            if match:
                ip = match.group(1)
                mac = match.group(2).upper().replace("-", ":")
                entry_type = match.group(3).lower()
                if not mac.startswith("FF:FF") and not mac.startswith("01:"):
                    ip_mac[ip] = {
                        "mac": mac,
                        "ip_type": "dhcp" if entry_type == "dynamic" else "static",
                    }
    except Exception:
        pass
    return ip_mac


def find_ip_by_mac(mac: str) -> str:
    """Return IP for a given MAC from the current ARP table, or empty string."""
    norm = mac.upper().replace("-", ":").replace(".", ":")
    for ip, entry in _parse_arp_table().items():
        if entry["mac"] == norm:
            return ip
    return ""


def _get_local_networks() -> list[ipaddress.IPv4Network]:
    """Detect local network ranges from active interfaces."""
    networks: list[ipaddress.IPv4Network] = []
    try:
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, timeout=5
        )
        ip_pattern = re.compile(r"IPv4[^:]*:\s*([\d.]+)")
        mask_pattern = re.compile(r"Subnet Mask[^:]*:\s*([\d.]+)")

        ip = None
        for line in result.stdout.splitlines():
            m = ip_pattern.search(line)
            if m:
                ip = m.group(1)
                continue
            m = mask_pattern.search(line)
            if m and ip:
                mask = m.group(1)
                try:
                    net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                    if not net.is_loopback and not net.is_link_local:
                        networks.append(net)
                except ValueError:
                    pass
                ip = None
    except Exception:
        pass
    return networks


def _check_port_open(ip: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def get_local_devices() -> list[dict]:
    """
    Le interfaces de rede locais via ipconfig /all.
    Suporta ipconfig em PT, EN e qualquer idioma — parseia por estrutura, nao por label.
    """
    devices: list[dict] = []
    try:
        result = subprocess.run(["ipconfig", "/all"], capture_output=True, timeout=5)
        # Tenta cp850 (Windows PT/BR) com fallback para latin-1
        try:
            output = result.stdout.decode("cp850")
        except Exception:
            output = result.stdout.decode("latin-1", errors="replace")

        # Normaliza quebras de linha
        lines = output.replace("\r\n", "\n").replace("\r", "\n").splitlines()

        # Coleta blocos de adaptador: linhas sem recuo que terminam em ":"
        # sao cabecalhos de adaptador
        adapters: list[tuple[str, list[str]]] = []
        current_name = ""
        current_lines: list[str] = []

        for line in lines:
            stripped = line.rstrip()
            if stripped and not stripped[0].isspace() and stripped.endswith(":"):
                if current_name and current_lines:
                    adapters.append((current_name, current_lines))
                current_name = stripped.rstrip(":")
                current_lines = []
            else:
                current_lines.append(line)

        if current_name and current_lines:
            adapters.append((current_name, current_lines))

        for adapter_name, block_lines in adapters:
            block = "\n".join(block_lines)

            # IP: linha com "(Preferencial)" ou "(Preferred)" — padrao do ipconfig
            ip = ""
            for line in block_lines:
                m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*\(Prefer", line)
                if m:
                    ip = m.group(1)
                    break
            # Fallback: qualquer linha com IPv4 no nome (EN/PT)
            if not ip:
                for line in block_lines:
                    if re.search(r"IPv4|Endere.{0,10}IP", line, re.IGNORECASE):
                        m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                        if m:
                            ip = m.group(1)
                            break

            if not ip:
                continue
            try:
                addr = ipaddress.IPv4Address(ip)
                if addr.is_loopback or addr.is_link_local or addr.is_unspecified:
                    continue
            except ValueError:
                continue

            # MAC: XX-XX-XX-XX-XX-XX (ipconfig sempre usa hifens)
            mac = ""
            mac_m = re.search(
                r"\b([\dA-Fa-f]{2}(?:-[\dA-Fa-f]{2}){5})\b", block
            )
            if mac_m:
                mac = mac_m.group(1).upper().replace("-", ":")

            # Mascara: 255.x.x.x
            netmask = ""
            mask_m = re.search(r"(255(?:\.\d{1,3}){3})", block)
            if mask_m:
                netmask = mask_m.group(1)

            # Gateway IPv4: pega todos os IPs apos a linha que contem "Gateway"
            # e retorna o primeiro que nao seja IPv6
            gateway = ""
            in_gw = False
            for line in block_lines:
                if re.search(r"Gateway|Padr", line, re.IGNORECASE):
                    in_gw = True
                if in_gw:
                    m = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", line)
                    if m:
                        try:
                            gw = ipaddress.IPv4Address(m.group(1))
                            if not gw.is_unspecified and not gw.is_loopback:
                                gateway = str(gw)
                                break
                        except ValueError:
                            pass
                    if in_gw and not line.strip() and gateway:
                        break

            # DHCP vs static: ipconfig /all expoe "DHCP Enabled . : Yes/No"
            ip_type = "static"
            lease_expires = ""
            for line in block_lines:
                # Linha contem "DHCP" mas nao e sobre o servidor (DHCP Server)
                if re.search(r"\bDHCP\b", line, re.IGNORECASE) and not re.search(
                    r"Server|Servidor|Pool", line, re.IGNORECASE
                ):
                    if re.search(r"\b(Yes|Sim|Oui|Ja)\b", line, re.IGNORECASE):
                        ip_type = "dhcp"
                    break
            if ip_type == "dhcp":
                for line in block_lines:
                    if re.search(r"Lease Exp|Concess.*expir|Bail.*expir|Expirac", line, re.IGNORECASE):
                        m = re.search(r":\s*(.+)$", line)
                        if m:
                            lease_expires = m.group(1).strip()
                        break

            devices.append({
                "ip":           ip,
                "mac":          mac,
                "hostname":     socket.gethostname(),
                "vendor":       "Local PC",
                "model":        adapter_name,
                "os_type":      "local",
                "status":       "online",
                "ssh_open":     False,
                "api_open":     False,
                "uptime":       "",
                "firmware":     "",
                "gateway":      gateway,
                "netmask":      netmask,
                "ip_type":      ip_type,
                "lease_expires": lease_expires,
            })

    except Exception:
        pass

    return devices


def scan_network(
    network: str = "",
    timeout_ms: int = 500,
    max_workers: int = 50,
    progress_cb: Callable[[str, int, int], None] | None = None,
    stop_event=None,
) -> list[dict]:
    """
    Sweep an IP range with concurrent pings, then read ARP table.
    Returns list of dicts with ip, mac, ssh_open, api_open, hostname.
    """
    # Determine networks to scan
    networks: list[ipaddress.IPv4Network] = []
    if network:
        try:
            networks = [ipaddress.IPv4Network(network, strict=False)]
        except ValueError:
            pass
    if not networks:
        networks = _get_local_networks()
    if not networks:
        networks = [ipaddress.IPv4Network("192.168.1.0/24")]

    all_hosts: list[str] = []
    for net in networks:
        # Skip very large networks to prevent hanging
        if net.num_addresses > 4096:
            continue
        all_hosts.extend([str(h) for h in net.hosts()])

    total = len(all_hosts)
    completed = 0

    # Concurrent ping flood to populate ARP cache
    def ping_host(ip: str) -> str:
        nonlocal completed
        if stop_event and stop_event.is_set():
            return ""
        _ping(ip, timeout_ms)
        completed += 1
        if progress_cb:
            progress_cb(ip, completed, total)
        return ip

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(ping_host, all_hosts))

    if stop_event and stop_event.is_set():
        return []

    # Read ARP table after ping flood
    arp_table = _parse_arp_table()

    results: list[dict] = []
    check_ips = set(all_hosts) & set(arp_table.keys())

    def check_device(ip: str) -> dict | None:
        if stop_event and stop_event.is_set():
            return None
        entry = arp_table.get(ip, {})
        mac = entry.get("mac", "")
        ip_type = entry.get("ip_type", "")
        ssh = _check_port_open(ip, 22, 0.4)
        api = _check_port_open(ip, 8728, 0.3)
        hostname = get_hostname(ip)
        return {"ip": ip, "mac": mac, "ip_type": ip_type, "ssh_open": ssh, "api_open": api, "hostname": hostname}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(check_device, ip) for ip in sorted(check_ips)]
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            if r:
                results.append(r)

    return results
