"""Auto Config page — automated device configuration wizard."""

import threading
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame, QGroupBox, QFormLayout,
    QTextEdit, QStackedWidget, QMessageBox, QCheckBox, QSpinBox,
)
from PySide6.QtCore import Qt, Signal, QObject

from app.database import db
from app.core.security import encrypt_credentials
from app.ui.styles import C_SUCCESS, C_ERROR, C_TEXT_DIM, C_WARNING


class _ConfigWorker(QObject):
    finished = Signal(bool, list)

    def __init__(self, ip: str, os_type: str, config_type: str, params: dict,
                 username: str, password: str):
        super().__init__()
        self.ip = ip
        self.os_type = os_type
        self.config_type = config_type
        self.params = params
        self.username = username
        self.password = password

    def run(self):
        success, messages = self._apply()
        if success and self.username:
            u_enc, p_enc = encrypt_credentials(self.username, self.password)
            db.save_credential(
                self.ip, u_enc, p_enc,
                device_type=self.os_type,
                port=8728 if self.os_type == "mikrotik" else 22,
                proto="api" if self.os_type == "mikrotik" else "ssh",
            )
        self.finished.emit(success, messages)

    def _apply(self) -> tuple[bool, list[str]]:
        template = {
            "name": f"{self.os_type}_{self.config_type}",
            "config_type": self.config_type,
            "params": self.params,
        }
        if self.os_type == "mikrotik":
            from app.devices.mikrotik import MikroTikConfig
            dev = MikroTikConfig(self.ip, self.username, self.password)
            if not dev.connect():
                return False, ["Falha ao conectar. Verifique IP e credenciais."]
            success, msgs = dev.apply_template(template)
            dev.disconnect()
            return success, msgs
        elif self.os_type == "ubiquiti":
            from app.devices.ubiquiti import UbiquitiConfig
            dev = UbiquitiConfig(self.ip, self.username, self.password)
            if not dev.connect():
                return False, ["Falha ao conectar via SSH. Verifique IP e credenciais."]
            success, msgs = dev.apply_template(template)
            dev.disconnect()
            return success, msgs
        return False, ["Tipo de dispositivo nao suportado"]


class AutoConfigPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Auto Config")
        title.setObjectName("page_title")
        layout.addWidget(title)

        sub = QLabel("Configure dispositivos MikroTik e Ubiquiti automaticamente")
        sub.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(sub)

        # ── Step 1: Device info ──
        conn_group = QGroupBox("1. Dispositivo e Conexao")
        conn_form = QFormLayout(conn_group)
        conn_form.setSpacing(10)

        self._ip_input = QLineEdit()
        self._ip_input.setPlaceholderText("192.168.1.1")
        conn_form.addRow("IP do Dispositivo:", self._ip_input)

        mac_row = QHBoxLayout()
        self._mac_input = QLineEdit()
        self._mac_input.setPlaceholderText("AA:BB:CC:DD:EE:FF  (MikroTik local — resolve via ARP)")
        mac_row.addWidget(self._mac_input, 1)
        btn_resolve = QPushButton("Resolver MAC")
        btn_resolve.setToolTip("Busca o IP do dispositivo na tabela ARP local")
        btn_resolve.clicked.connect(self._resolve_mac)
        mac_row.addWidget(btn_resolve)
        conn_form.addRow("MAC (opcional):", mac_row)

        self._os_combo = QComboBox()
        self._os_combo.addItems(["MikroTik", "Ubiquiti"])
        self._os_combo.currentTextChanged.connect(self._on_os_changed)
        conn_form.addRow("Tipo de Equipamento:", self._os_combo)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["AP (Access Point)", "Cliente (Station)", "Bridge", "Repetidor"])
        conn_form.addRow("Modo de Configuracao:", self._type_combo)

        layout.addWidget(conn_group)

        # ── Step 2: Credentials ──
        cred_group = QGroupBox("2. Credenciais")
        cred_form = QFormLayout(cred_group)
        cred_form.setSpacing(10)

        self._user_input = QLineEdit()
        self._user_input.setPlaceholderText("admin")
        self._user_input.setText("admin")
        cred_form.addRow("Usuario:", self._user_input)

        self._pass_input = QLineEdit()
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.setPlaceholderText("Deixe vazio para nenhuma senha")
        cred_form.addRow("Senha:", self._pass_input)

        self._auto_login_check = QCheckBox("Tentar login automatico (admin/admin, ubnt/ubnt)")
        cred_form.addRow("", self._auto_login_check)

        layout.addWidget(cred_group)

        # ── Step 3: Parameters (stacked by OS) ──
        self._params_stack = QStackedWidget()

        # MikroTik params
        self._mktik_widget = self._build_mikrotik_params()
        self._params_stack.addWidget(self._mktik_widget)

        # Ubiquiti params
        self._ubnt_widget = self._build_ubnt_params()
        self._params_stack.addWidget(self._ubnt_widget)

        layout.addWidget(self._params_stack)

        # ── Apply button ──
        btn_row = QHBoxLayout()
        self._btn_auto_login = QPushButton("  Detectar Login Automatico")
        self._btn_auto_login.clicked.connect(self._do_auto_login)
        btn_row.addWidget(self._btn_auto_login)

        btn_row.addStretch()

        self._btn_apply = QPushButton("  Aplicar Configuracao")
        self._btn_apply.setObjectName("btn_primary")
        self._btn_apply.setMinimumWidth(200)
        self._btn_apply.setMinimumHeight(40)
        self._btn_apply.clicked.connect(self._apply_config)
        btn_row.addWidget(self._btn_apply)

        layout.addLayout(btn_row)

        # ── Output log ──
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumHeight(160)
        self._output.setPlaceholderText("Resultado da configuracao aparecera aqui...")
        layout.addWidget(self._output)

    def _build_mikrotik_params(self) -> QWidget:
        w = QWidget()
        group = QGroupBox("3. Parametros MikroTik")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._mk_ssid = QLineEdit()
        self._mk_ssid.setPlaceholderText("MinhaRede")
        form.addRow("SSID (nome da rede):", self._mk_ssid)

        self._mk_pass = QLineEdit()
        self._mk_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._mk_pass.setPlaceholderText("minima 8 caracteres")
        form.addRow("Senha WiFi:", self._mk_pass)

        self._mk_ip = QLineEdit()
        self._mk_ip.setPlaceholderText("192.168.88.1/24")
        form.addRow("IP da Interface LAN:", self._mk_ip)

        self._mk_pool = QLineEdit()
        self._mk_pool.setPlaceholderText("192.168.88.10-192.168.88.200")
        form.addRow("Pool DHCP:", self._mk_pool)

        self._mk_dns = QLineEdit()
        self._mk_dns.setPlaceholderText("8.8.8.8")
        self._mk_dns.setText("8.8.8.8")
        form.addRow("DNS:", self._mk_dns)

        self._mk_nat = QCheckBox("Habilitar NAT Masquerade")
        self._mk_nat.setChecked(True)
        form.addRow("", self._mk_nat)

        self._mk_wan = QLineEdit()
        self._mk_wan.setPlaceholderText("ether1")
        self._mk_wan.setText("ether1")
        form.addRow("Interface WAN:", self._mk_wan)

        self._mk_lan = QLineEdit()
        self._mk_lan.setPlaceholderText("ether2")
        self._mk_lan.setText("ether2")
        form.addRow("Interface LAN:", self._mk_lan)

        self._mk_wlan = QLineEdit()
        self._mk_wlan.setPlaceholderText("wlan1")
        self._mk_wlan.setText("wlan1")
        form.addRow("Interface Wireless:", self._mk_wlan)

        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(group)
        return w

    def _build_ubnt_params(self) -> QWidget:
        w = QWidget()
        group = QGroupBox("3. Parametros Ubiquiti")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._ub_ssid = QLineEdit()
        self._ub_ssid.setPlaceholderText("MinhaRede")
        form.addRow("SSID:", self._ub_ssid)

        self._ub_pass = QLineEdit()
        self._ub_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._ub_pass.setPlaceholderText("minima 8 caracteres")
        form.addRow("Senha WPA2:", self._ub_pass)

        self._ub_channel = QSpinBox()
        self._ub_channel.setRange(1, 161)
        self._ub_channel.setValue(6)
        form.addRow("Canal:", self._ub_channel)

        self._ub_txpower = QSpinBox()
        self._ub_txpower.setRange(1, 30)
        self._ub_txpower.setValue(20)
        form.addRow("Potencia TX (dBm):", self._ub_txpower)

        self._ub_ip = QLineEdit()
        self._ub_ip.setPlaceholderText("192.168.1.20")
        form.addRow("IP Estatico:", self._ub_ip)

        self._ub_mask = QLineEdit()
        self._ub_mask.setPlaceholderText("255.255.255.0")
        self._ub_mask.setText("255.255.255.0")
        form.addRow("Mascara:", self._ub_mask)

        self._ub_gw = QLineEdit()
        self._ub_gw.setPlaceholderText("192.168.1.1")
        form.addRow("Gateway:", self._ub_gw)

        self._ub_dns = QLineEdit()
        self._ub_dns.setPlaceholderText("8.8.8.8")
        self._ub_dns.setText("8.8.8.8")
        form.addRow("DNS:", self._ub_dns)

        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(group)
        return w

    def _on_os_changed(self, text: str):
        idx = 0 if text == "MikroTik" else 1
        self._params_stack.setCurrentIndex(idx)
        # Update default username
        self._user_input.setText("admin" if idx == 0 else "ubnt")

    def _do_auto_login(self):
        ip = self._ip_input.text().strip()
        if not ip:
            self._log("Informe o IP do dispositivo.", C_WARNING)
            return

        os_type = self._os_combo.currentText().lower()
        self._log(f"Tentando login automatico em {ip}...")
        self._btn_apply.setEnabled(False)

        def _try():
            success, user, passwd = False, "", ""
            try:
                if os_type == "mikrotik":
                    from app.devices.mikrotik import MikroTikConfig
                    dev = MikroTikConfig(ip)
                    success, user, passwd = dev.auto_login()
                    dev.disconnect()
                else:
                    from app.devices.ubiquiti import UbiquitiConfig
                    dev = UbiquitiConfig(ip)
                    success, user, passwd = dev.auto_login()
                    dev.disconnect()
            except Exception as e:
                success = False
                user = str(e)
            self._on_auto_login_result(success, user, passwd)

        threading.Thread(target=_try, daemon=True).start()

    def _on_auto_login_result(self, success: bool, user: str, passwd: str):
        self._btn_apply.setEnabled(True)
        if success:
            self._user_input.setText(user)
            self._pass_input.setText(passwd)
            self._log(f"Login encontrado: {user} / {'*' * len(passwd)}", C_SUCCESS)
        else:
            self._log("Nenhuma credencial padrao funcionou.", C_ERROR)

    def _apply_config(self):
        ip = self._ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "Aviso", "Informe o IP do dispositivo.")
            return

        os_type = self._os_combo.currentText().lower()
        config_type_raw = self._type_combo.currentText()
        config_type = "ap" if "AP" in config_type_raw else \
                      "client" if "Cliente" in config_type_raw else \
                      "bridge" if "Bridge" in config_type_raw else "repeater"

        username = self._user_input.text().strip()
        password = self._pass_input.text()
        params = self._collect_params(os_type)

        self._log(f"Aplicando configuracao {config_type} em {ip} ({os_type})...")
        self._btn_apply.setEnabled(False)

        worker = _ConfigWorker(ip, os_type, config_type, params, username, password)

        def _run():
            worker.run()

        worker.finished.connect(self._on_config_done)
        threading.Thread(target=_run, daemon=True).start()

    def _collect_params(self, os_type: str) -> dict:
        if os_type == "mikrotik":
            return {
                "ssid":      self._mk_ssid.text().strip(),
                "password":  self._mk_pass.text(),
                "ip":        self._mk_ip.text().strip(),
                "dhcp_pool": self._mk_pool.text().strip(),
                "dns":       self._mk_dns.text().strip(),
                "nat":       self._mk_nat.isChecked(),
                "wan_iface": self._mk_wan.text().strip(),
                "lan_iface": self._mk_lan.text().strip(),
                "wlan_iface":self._mk_wlan.text().strip(),
                "gateway":   self._mk_ip.text().strip().split("/")[0] if self._mk_ip.text() else "",
            }
        else:
            return {
                "ssid":     self._ub_ssid.text().strip(),
                "password": self._ub_pass.text(),
                "channel":  self._ub_channel.value(),
                "txpower":  self._ub_txpower.value(),
                "ip":       self._ub_ip.text().strip(),
                "netmask":  self._ub_mask.text().strip(),
                "gateway":  self._ub_gw.text().strip(),
                "dns":      self._ub_dns.text().strip(),
            }

    def _on_config_done(self, success: bool, messages: list):
        self._btn_apply.setEnabled(True)
        color = C_SUCCESS if success else C_ERROR
        self._log(f"\n{'CONFIG OK' if success else 'CONFIG FALHOU'}:", color)
        for msg in messages:
            self._log(f"  {msg}", color)

    def _log(self, msg: str, color: str = ""):
        if color:
            self._output.append(f'<span style="color:{color}">{msg}</span>')
        else:
            self._output.append(msg)

    def _resolve_mac(self):
        mac = self._mac_input.text().strip()
        if not mac:
            self._log("Informe o MAC Address.", C_WARNING)
            return
        from app.network.arp_scan import find_ip_by_mac
        ip = find_ip_by_mac(mac)
        if ip:
            self._ip_input.setText(ip)
            self._log(f"MAC {mac}  →  IP {ip}", C_SUCCESS)
        else:
            self._log(
                f"MAC {mac} nao encontrado na tabela ARP. "
                "Execute um scan de rede ou conecte o cabo antes de tentar.", C_WARNING
            )

    def prefill(self, ip: str, os_type: str, mac: str = ""):
        self._ip_input.setText(ip)
        if mac:
            self._mac_input.setText(mac)
        idx = 0 if os_type == "mikrotik" else 1
        self._os_combo.setCurrentIndex(idx)
