"""Settings page — application configuration."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QCheckBox, QGroupBox, QFormLayout,
    QFrame,
)
from PySide6.QtCore import Qt

from app.core.config import config
from app.ui.styles import C_TEXT_DIM, C_SUCCESS


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Configuracoes do Sistema")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # ── Scan settings ──
        scan_group = QGroupBox("Configuracoes de Scan")
        scan_form = QFormLayout(scan_group)
        scan_form.setSpacing(10)

        self._scan_range = QLineEdit()
        self._scan_range.setPlaceholderText("Ex: 192.168.1.0/24 (vazio = auto-detectar)")
        scan_form.addRow("Faixa de Scan:", self._scan_range)

        self._ping_timeout = QSpinBox()
        self._ping_timeout.setRange(100, 5000)
        self._ping_timeout.setSuffix(" ms")
        scan_form.addRow("Timeout de Ping:", self._ping_timeout)

        self._scan_threads = QSpinBox()
        self._scan_threads.setRange(10, 200)
        self._scan_threads.setSuffix(" threads")
        scan_form.addRow("Threads de Scan:", self._scan_threads)

        self._auto_scan = QCheckBox("Habilitar scan automatico em intervalo")
        scan_form.addRow("", self._auto_scan)

        self._auto_scan_interval = QSpinBox()
        self._auto_scan_interval.setRange(60, 3600)
        self._auto_scan_interval.setSuffix(" segundos")
        scan_form.addRow("Intervalo do Scan Auto:", self._auto_scan_interval)

        layout.addWidget(scan_group)

        # ── Connection settings ──
        conn_group = QGroupBox("Configuracoes de Conexao")
        conn_form = QFormLayout(conn_group)
        conn_form.setSpacing(10)

        self._ssh_port = QSpinBox()
        self._ssh_port.setRange(1, 65535)
        conn_form.addRow("Porta SSH Padrao:", self._ssh_port)

        self._api_port = QSpinBox()
        self._api_port.setRange(1, 65535)
        conn_form.addRow("Porta API MikroTik:", self._api_port)

        self._mk_user = QLineEdit()
        self._mk_user.setPlaceholderText("admin")
        conn_form.addRow("Usuario MikroTik Padrao:", self._mk_user)

        self._ub_user = QLineEdit()
        self._ub_user.setPlaceholderText("ubnt")
        conn_form.addRow("Usuario Ubiquiti Padrao:", self._ub_user)

        layout.addWidget(conn_group)

        # ── Storage ──
        storage_group = QGroupBox("Armazenamento")
        storage_form = QFormLayout(storage_group)
        storage_form.setSpacing(10)

        self._db_path = QLineEdit()
        self._db_path.setReadOnly(True)
        self._db_path.setStyleSheet(f"color: {C_TEXT_DIM};")
        storage_form.addRow("Banco de Dados:", self._db_path)

        self._log_path = QLineEdit()
        self._log_path.setReadOnly(True)
        self._log_path.setStyleSheet(f"color: {C_TEXT_DIM};")
        storage_form.addRow("Arquivo de Log:", self._log_path)

        layout.addWidget(storage_group)

        # ── Save button ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_save = QPushButton("  Salvar Configuracoes")
        self._btn_save.setObjectName("btn_primary")
        self._btn_save.setMinimumWidth(200)
        self._btn_save.setMinimumHeight(38)
        self._btn_save.clicked.connect(self._save)
        btn_row.addWidget(self._btn_save)

        btn_defaults = QPushButton("Restaurar Padroes")
        btn_defaults.clicked.connect(self._restore_defaults)
        btn_row.addWidget(btn_defaults)

        layout.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {C_SUCCESS};")
        layout.addWidget(self._status)

        layout.addStretch()

        # ── About ──
        about = QFrame()
        about.setObjectName("card")
        about_layout = QVBoxLayout(about)
        about_layout.setContentsMargins(16, 12, 16, 12)
        info = QLabel(
            "FieldTool v1.0\n"
            "Ferramenta de campo para redes — 100% Offline\n"
            "Suporte: MikroTik (RouterOS API) | Ubiquiti (SSH/UCI)"
        )
        info.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 12px;")
        about_layout.addWidget(info)
        layout.addWidget(about)

    def _load_values(self):
        self._scan_range.setText(config.get("scan_range", ""))
        self._ping_timeout.setValue(config.get("ping_timeout_ms", 500))
        self._scan_threads.setValue(config.get("scan_threads", 50))
        self._auto_scan.setChecked(config.get("auto_scan", False))
        self._auto_scan_interval.setValue(config.get("auto_scan_interval", 300))
        self._ssh_port.setValue(config.get("default_ssh_port", 22))
        self._api_port.setValue(config.get("default_api_port", 8728))
        self._mk_user.setText(config.get("default_mikrotik_user", "admin"))
        self._ub_user.setText(config.get("default_ubnt_user", "ubnt"))
        self._db_path.setText(config.get("db_path", ""))
        self._log_path.setText(config.get("log_path", ""))

    def _save(self):
        config.update({
            "scan_range":            self._scan_range.text().strip(),
            "ping_timeout_ms":       self._ping_timeout.value(),
            "scan_threads":          self._scan_threads.value(),
            "auto_scan":             self._auto_scan.isChecked(),
            "auto_scan_interval":    self._auto_scan_interval.value(),
            "default_ssh_port":      self._ssh_port.value(),
            "default_api_port":      self._api_port.value(),
            "default_mikrotik_user": self._mk_user.text().strip(),
            "default_ubnt_user":     self._ub_user.text().strip(),
        })
        self._status.setText("Configuracoes salvas com sucesso.")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._status.setText(""))

    def _restore_defaults(self):
        from app.core.config import DEFAULTS
        config.update(DEFAULTS)
        self._load_values()
        self._status.setText("Padroes restaurados.")
