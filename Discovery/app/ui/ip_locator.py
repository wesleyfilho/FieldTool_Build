"""IP Locator page — search by IP or MAC."""

import socket
import subprocess
import re
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFrame, QGridLayout, QTextEdit,
)
from PySide6.QtCore import Qt, Signal, QObject

from app.network.oui import lookup_vendor
from app.database import db
from app.ui.styles import C_SUCCESS, C_ERROR, C_TEXT_DIM, C_ACCENT2, C_MKTIK, C_UBNT, OS_COLORS


class _Worker(QObject):
    result = Signal(dict)
    error  = Signal(str)

    def __init__(self, query: str):
        super().__init__()
        self._query = query.strip()

    def run(self):
        try:
            data = self._lookup()
            self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))

    def _lookup(self) -> dict:
        query = self._query
        data: dict = {"query": query}

        # Determine if IP or MAC
        is_mac = bool(re.match(r"^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$", query))
        is_ip  = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", query))

        if is_mac:
            data["mac"] = query.upper().replace("-", ":")
            data["vendor"] = lookup_vendor(query)
            # Try to find IP from ARP
            ip = self._find_ip_for_mac(query)
            if ip:
                data["ip"] = ip
                is_ip = True
                query = ip

        if is_ip:
            data["ip"] = query
            data["latency"] = self._ping_latency(query)
            data["hostname"] = self._resolve_hostname(query)
            # Get ARP entry
            mac = self._arp_lookup(query)
            if mac and not data.get("mac"):
                data["mac"] = mac
            if data.get("mac") and not data.get("vendor"):
                data["vendor"] = lookup_vendor(data["mac"])
            # Get gateway / mask from route
            gw, mask, iface = self._get_route_info(query)
            data["gateway"] = gw
            data["netmask"] = mask
            data["interface"] = iface
            data["dns"] = self._get_dns()
            # Check DB
            db_dev = self._find_in_db(query)
            if db_dev:
                data["db_model"] = db_dev.get("model", "")
                data["db_os"]    = db_dev.get("os_type", "")
                data["db_uptime"]= db_dev.get("uptime", "")
                data["ssh_open"] = bool(db_dev.get("ssh_open"))
                data["api_open"] = bool(db_dev.get("api_open"))

        return data

    def _ping_latency(self, ip: str) -> str:
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", ip],
                capture_output=True, text=True, timeout=3
            )
            m = re.search(r"Average = (\d+)ms", result.stdout)
            if m:
                return f"{m.group(1)} ms"
            m = re.search(r"tempo[=<](\d+)ms", result.stdout)
            if m:
                return f"{m.group(1)} ms"
        except Exception:
            pass
        return "Timeout"

    def _resolve_hostname(self, ip: str) -> str:
        try:
            return socket.gethostbyaddr(ip)[0]
        except Exception:
            return ""

    def _arp_lookup(self, ip: str) -> str:
        try:
            result = subprocess.run(["arp", "-a", ip], capture_output=True, text=True, timeout=3)
            m = re.search(
                r"([\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2}[-:][\da-fA-F]{2})",
                result.stdout
            )
            if m:
                return m.group(1).upper().replace("-", ":")
        except Exception:
            pass
        return ""

    def _find_ip_for_mac(self, mac: str) -> str:
        norm = mac.upper().replace("-", ":").replace(".", ":")
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=3)
            for line in result.stdout.splitlines():
                if norm in line.upper():
                    m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                    if m:
                        return m.group(1)
        except Exception:
            pass
        return ""

    def _get_route_info(self, ip: str) -> tuple[str, str, str]:
        try:
            result = subprocess.run(
                ["route", "print", "-4"], capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[0] == "0.0.0.0":
                    return parts[2], parts[1], parts[3] if len(parts) > 3 else ""
        except Exception:
            pass
        return "", "", ""

    def _get_dns(self) -> str:
        try:
            result = subprocess.run(
                ["ipconfig", "/all"], capture_output=True, text=True, timeout=3
            )
            m = re.search(r"DNS[^:]*:\s*([\d.]+)", result.stdout)
            if m:
                return m.group(1)
        except Exception:
            pass
        return ""

    def _find_in_db(self, ip: str) -> dict | None:
        devices = db.get_all_devices()
        return next((d for d in devices if d.get("ip") == ip), None)


def _info_row(label: str, value: str, color: str = "") -> tuple[QLabel, QLabel]:
    lbl = QLabel(label + ":")
    lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 12px;")
    val = QLabel(value or "—")
    if color:
        val.setStyleSheet(f"color: {color}; font-weight: bold;")
    else:
        val.setStyleSheet("font-weight: 500;")
    val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl, val


class IPLocatorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker_thread: threading.Thread | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("IP Locator")
        title.setObjectName("page_title")
        layout.addWidget(title)

        sub = QLabel("Busque informacoes detalhadas por IP ou MAC Address")
        sub.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(sub)

        # ── Search bar ──
        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Digite um IP (192.168.1.1) ou MAC (AA:BB:CC:DD:EE:FF)")
        self._search_input.setMinimumHeight(40)
        self._search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_input, 1)

        self._btn_search = QPushButton("  Localizar")
        self._btn_search.setObjectName("btn_primary")
        self._btn_search.setMinimumHeight(40)
        self._btn_search.setMinimumWidth(120)
        self._btn_search.clicked.connect(self._do_search)
        search_row.addWidget(self._btn_search)
        layout.addLayout(search_row)

        # ── Results card ──
        self._result_card = QFrame()
        self._result_card.setObjectName("card")
        self._result_card.setVisible(False)
        result_layout = QVBoxLayout(self._result_card)
        result_layout.setContentsMargins(20, 16, 20, 16)
        result_layout.setSpacing(8)

        self._result_title = QLabel("")
        self._result_title.setObjectName("section_title")
        result_layout.addWidget(self._result_title)

        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(24)
        self._grid.setVerticalSpacing(8)
        result_layout.addLayout(self._grid)

        layout.addWidget(self._result_card)
        layout.addStretch()

        # ── Status ──
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(self._status_label)

    def _do_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._status_label.setText("Buscando...")
        self._btn_search.setEnabled(False)
        self._result_card.setVisible(False)

        worker = _Worker(query)
        worker.result.connect(self._on_result)
        worker.error.connect(self._on_error)

        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

    def _on_result(self, data: dict):
        self._btn_search.setEnabled(True)
        self._status_label.setText("")
        self._show_result(data)

    def _on_error(self, msg: str):
        self._btn_search.setEnabled(True)
        self._status_label.setText(f"Erro: {msg}")

    def _show_result(self, d: dict):
        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ip = d.get("ip", "")
        mac = d.get("mac", "")
        self._result_title.setText(f"Resultado: {ip or mac or d.get('query','')}")

        rows = [
            ("IP",          d.get("ip", ""),        ""),
            ("MAC",         d.get("mac", ""),        ""),
            ("Fabricante",  d.get("vendor", ""),     C_ACCENT2),
            ("Hostname",    d.get("hostname", ""),   ""),
            ("Latencia",    d.get("latency", ""),    C_SUCCESS if d.get("latency","") != "Timeout" else C_ERROR),
            ("Gateway",     d.get("gateway", ""),    ""),
            ("Mascara",     d.get("netmask", ""),    ""),
            ("DNS",         d.get("dns", ""),        ""),
            ("Interface",   d.get("interface", ""),  ""),
            ("SSH Aberto",  "Sim" if d.get("ssh_open") else "Nao",
             C_SUCCESS if d.get("ssh_open") else C_ERROR),
            ("API MikroTik","Sim" if d.get("api_open") else "Nao",
             C_SUCCESS if d.get("api_open") else C_ERROR),
            ("Modelo (DB)", d.get("db_model", ""),  ""),
            ("Tipo (DB)",   d.get("db_os", ""),      OS_COLORS.get(d.get("db_os",""), "")),
            ("Uptime (DB)", d.get("db_uptime", ""), ""),
        ]

        for i, (label, value, color) in enumerate(rows):
            if not value:
                continue
            lbl, val = _info_row(label, value, color)
            col = (i % 2) * 2
            row = i // 2
            self._grid.addWidget(lbl, row, col)
            self._grid.addWidget(val, row, col + 1)

        self._result_card.setVisible(True)
