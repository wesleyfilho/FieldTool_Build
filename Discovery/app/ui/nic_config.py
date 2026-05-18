"""NIC Configurator — set PC network adapter for direct Ubiquiti/MikroTik access."""

import subprocess
import re
import threading
import ctypes

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QGroupBox, QFormLayout, QTextEdit,
)
from PySide6.QtCore import Qt, Signal

from app.ui.styles import C_SUCCESS, C_ERROR, C_TEXT_DIM, C_WARNING, C_UBNT, C_MKTIK


PRESETS = {
    "Ubiquiti": {"ip": "192.168.1.10", "mask": "255.255.255.0", "gw": "192.168.1.1", "dns": "8.8.8.8"},
}


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _netsh(*args) -> tuple[bool, str]:
    try:
        result = subprocess.run(["netsh", *args], capture_output=True, timeout=10)
        try:
            out = (result.stdout + result.stderr).decode("cp850")
        except Exception:
            out = (result.stdout + result.stderr).decode("latin-1", errors="replace")
        return result.returncode == 0, out.strip()
    except Exception as e:
        return False, str(e)


def _get_interfaces() -> list[str]:
    _, out = _netsh("interface", "show", "interface")
    names = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped or "---" in stripped:
            continue
        if re.match(r"Admin|Estado|Type|Tipo", stripped, re.IGNORECASE):
            continue
        # Columns: AdminState  State  Type  Name (name may contain spaces)
        m = re.match(r"\S+\s+\S+\s+\S+\s+(.*)", stripped)
        if m:
            name = m.group(1).strip()
            if name:
                names.append(name)
    return names


def _get_iface_config(iface: str) -> dict:
    _, out = _netsh("interface", "ip", "show", "config", iface)
    data: dict = {}
    for line in out.splitlines():
        # DHCP enabled
        if re.search(r"DHCP", line, re.IGNORECASE) and re.search(r"Enabled|Habilitado", line, re.IGNORECASE):
            data["dhcp"] = bool(re.search(r"\b(Yes|Sim)\b", line, re.IGNORECASE))
        # IP (skip lines with / to avoid subnet prefix)
        if "ip" not in data and re.search(r"IP Address|Endere", line, re.IGNORECASE) and "/" not in line:
            m = re.search(r"((?:\d{1,3}\.){3}\d{1,3})", line)
            if m and not m.group(1).startswith("0."):
                data["ip"] = m.group(1)
        # Mask (always inside parentheses: "mask 255.255.255.0")
        m = re.search(r"mask\s+((?:\d{1,3}\.){3}\d{1,3})", line, re.IGNORECASE)
        if m:
            data["mask"] = m.group(1)
        # Gateway
        if "gw" not in data and re.search(r"Gateway", line, re.IGNORECASE):
            m = re.search(r"((?:\d{1,3}\.){3}\d{1,3})", line)
            if m and not m.group(1).startswith("0."):
                data["gw"] = m.group(1)
        # DNS
        if "dns" not in data and re.search(r"DNS", line, re.IGNORECASE):
            m = re.search(r"((?:\d{1,3}\.){3}\d{1,3})", line)
            if m:
                data["dns"] = m.group(1)
    return data


class NICConfigPage(QWidget):
    _log_sig    = Signal(str, str)   # message, color
    _status_sig = Signal(str)        # current config summary
    _btn_sig    = Signal(str, bool)  # "apply"|"dhcp", enabled

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_sig.connect(self._append_log)
        self._status_sig.connect(self._update_status)
        self._btn_sig.connect(self._set_btn)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Configurar Placa de Rede")
        title.setObjectName("page_title")
        layout.addWidget(title)

        sub = QLabel("Configure o adaptador do PC para acessar antenas Ubiquiti e MikroTik diretamente")
        sub.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(sub)

        if not _is_admin():
            warn = QLabel(
                "  Execute o programa como Administrador para aplicar configuracoes de rede."
            )
            warn.setStyleSheet(
                f"color: {C_WARNING}; background: #2d2000; "
                f"border: 1px solid {C_WARNING}; border-radius: 6px; padding: 8px;"
            )
            layout.addWidget(warn)

        # ── Adaptador ──
        adapter_group = QGroupBox("Adaptador de Rede")
        adapter_row = QHBoxLayout(adapter_group)

        self._iface_combo = QComboBox()
        self._iface_combo.setMinimumWidth(200)
        self._iface_combo.currentTextChanged.connect(self._refresh_status)
        adapter_row.addWidget(self._iface_combo)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {C_TEXT_DIM};")
        adapter_row.addWidget(self._status_lbl, 1)

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.clicked.connect(self._load_interfaces)
        adapter_row.addWidget(btn_refresh)

        layout.addWidget(adapter_group)

        # ── Presets ──
        preset_group = QGroupBox("Preset Rapido")
        preset_row = QHBoxLayout(preset_group)

        btn_ubnt = QPushButton("  Ubiquiti  192.168.1.x")
        btn_ubnt.setStyleSheet(f"color: {C_UBNT}; border-color: {C_UBNT};")
        btn_ubnt.clicked.connect(lambda: self._fill_preset("Ubiquiti"))
        preset_row.addWidget(btn_ubnt)

        preset_row.addStretch()
        layout.addWidget(preset_group)

        # ── Campos IP ──
        config_group = QGroupBox("Configuracao IP")
        form = QFormLayout(config_group)
        form.setSpacing(10)

        self._ip_in   = QLineEdit(); self._ip_in.setPlaceholderText("192.168.1.10")
        self._mask_in = QLineEdit(); self._mask_in.setText("255.255.255.0")
        self._gw_in   = QLineEdit(); self._gw_in.setPlaceholderText("192.168.1.1")
        self._dns_in  = QLineEdit(); self._dns_in.setText("8.8.8.8")

        form.addRow("IP:", self._ip_in)
        form.addRow("Mascara:", self._mask_in)
        form.addRow("Gateway:", self._gw_in)
        form.addRow("DNS:", self._dns_in)
        layout.addWidget(config_group)

        # ── Botoes ──
        btn_row = QHBoxLayout()

        self._btn_apply = QPushButton("  Aplicar IP Estatico")
        self._btn_apply.setObjectName("btn_primary")
        self._btn_apply.setMinimumHeight(40)
        self._btn_apply.setMinimumWidth(180)
        self._btn_apply.clicked.connect(self._apply_static)
        btn_row.addWidget(self._btn_apply)

        btn_row.addStretch()

        self._btn_dhcp = QPushButton("  Restaurar DHCP")
        self._btn_dhcp.setObjectName("btn_success")
        self._btn_dhcp.setMinimumHeight(40)
        self._btn_dhcp.setMinimumWidth(160)
        self._btn_dhcp.clicked.connect(self._restore_dhcp)
        btn_row.addWidget(self._btn_dhcp)

        layout.addLayout(btn_row)

        # ── Log ──
        self._log_out = QTextEdit()
        self._log_out.setReadOnly(True)
        self._log_out.setMaximumHeight(140)
        self._log_out.setPlaceholderText("Log de operacoes...")
        layout.addWidget(self._log_out)

        self._load_interfaces()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _load_interfaces(self):
        self._iface_combo.blockSignals(True)
        current = self._iface_combo.currentText()
        self._iface_combo.clear()
        for name in _get_interfaces():
            self._iface_combo.addItem(name)
        idx = self._iface_combo.findText(current)
        if idx >= 0:
            self._iface_combo.setCurrentIndex(idx)
        self._iface_combo.blockSignals(False)
        self._refresh_status(self._iface_combo.currentText())

    def _refresh_status(self, name: str):
        if not name:
            return
        cfg = _get_iface_config(name)
        if cfg.get("ip"):
            ip_type = "DHCP" if cfg.get("dhcp") else "Estatico"
            self._status_lbl.setText(
                f"{ip_type}  |  IP: {cfg['ip']}  |  GW: {cfg.get('gw', '—')}"
            )
        else:
            self._status_lbl.setText("Sem IP configurado / desconectado")

    def _fill_preset(self, preset: str):
        p = PRESETS[preset]
        self._ip_in.setText(p["ip"])
        self._mask_in.setText(p["mask"])
        self._gw_in.setText(p["gw"])
        self._dns_in.setText(p["dns"])

    def _apply_static(self):
        iface = self._iface_combo.currentText()
        ip    = self._ip_in.text().strip()
        mask  = self._mask_in.text().strip()
        gw    = self._gw_in.text().strip()
        dns   = self._dns_in.text().strip()

        if not iface or not ip:
            self._log_sig.emit("Selecione um adaptador e informe o IP.", C_WARNING)
            return

        self._btn_sig.emit("apply", False)
        self._log_sig.emit(f"Aplicando {ip}/{mask} gw {gw} em '{iface}'...", "")

        def _run():
            ok, out = _netsh("interface", "ip", "set", "address", iface, "static", ip, mask, gw)
            if ok or not out or "Ok" in out:
                self._log_sig.emit(f"IP aplicado: {ip}  mascara: {mask}  gateway: {gw}", C_SUCCESS)
                if dns:
                    ok2, _ = _netsh("interface", "ip", "set", "dns", iface, "static", dns)
                    self._log_sig.emit(
                        f"DNS {dns}: {'OK' if ok2 else 'ERRO'}",
                        C_SUCCESS if ok2 else C_ERROR,
                    )
            else:
                self._log_sig.emit(f"Erro: {out}", C_ERROR)
            self._btn_sig.emit("apply", True)
            self._status_sig.emit(iface)

        threading.Thread(target=_run, daemon=True).start()

    def _restore_dhcp(self):
        iface = self._iface_combo.currentText()
        if not iface:
            return

        self._btn_sig.emit("dhcp", False)
        self._log_sig.emit(f"Restaurando DHCP em '{iface}'...", "")

        def _run():
            ok, out = _netsh("interface", "ip", "set", "address", iface, "dhcp")
            if ok or not out or "Ok" in out:
                self._log_sig.emit("DHCP restaurado.", C_SUCCESS)
                _netsh("interface", "ip", "set", "dns", iface, "dhcp")
            else:
                self._log_sig.emit(f"Erro: {out}", C_ERROR)
            self._btn_sig.emit("dhcp", True)
            self._status_sig.emit(iface)

        threading.Thread(target=_run, daemon=True).start()

    # ── Slots (main thread) ──────────────────────────────────────────────────

    def _append_log(self, msg: str, color: str):
        if color:
            self._log_out.append(f'<span style="color:{color}">{msg}</span>')
        else:
            self._log_out.append(msg)

    def _update_status(self, iface: str):
        self._refresh_status(iface)

    def _set_btn(self, which: str, enabled: bool):
        if which == "apply":
            self._btn_apply.setEnabled(enabled)
        else:
            self._btn_dhcp.setEnabled(enabled)

    def on_activate(self):
        self._load_interfaces()
