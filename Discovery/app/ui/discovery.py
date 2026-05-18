"""Discovery page — real-time network scan with device table."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QMenu, QMessageBox, QProgressBar, QFrame,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QAction

from app.network.scanner import ScanThread
from app.database import db
from app.ui.styles import OS_COLORS, C_SUCCESS, C_ERROR, C_TEXT_DIM, C_MKTIK, C_UBNT


COLUMNS = [
    ("",         50,  False),
    ("IP",       130, False),
    ("MAC",      140, False),
    ("Fabricante",130, True),
    ("Hostname", 140, True),
    ("Modelo",   120, True),
    ("Tipo",     90,  False),
    ("SSH",      50,  False),
    ("API",      50,  False),
    ("Firmware", 110, True),
    ("Uptime",   100, True),
    ("Visto",    130, False),
]


class DiscoveryPage(QWidget):
    scan_finished = Signal()
    status_changed = Signal(str)
    scan_progress = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_thread: ScanThread | None = None
        self._devices: dict[str, dict] = {}
        self._filter = ""
        self._build_ui()
        self._load_from_db()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("Discovery de Rede")
        title.setObjectName("page_title")
        header.addWidget(title)
        header.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("  Buscar IP, MAC, Hostname...")
        self._search.setMinimumWidth(240)
        self._search.textChanged.connect(self._apply_filter)
        header.addWidget(self._search)

        self._btn_scan = QPushButton("  Iniciar Scan")
        self._btn_scan.setObjectName("btn_primary")
        self._btn_scan.setMinimumWidth(130)
        self._btn_scan.clicked.connect(self._start_scan)
        header.addWidget(self._btn_scan)

        self._btn_stop = QPushButton("  Parar")
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_scan)
        header.addWidget(self._btn_stop)

        layout.addLayout(header)

        # ── Progress ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumHeight(6)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(self._progress_label)

        # ── Table ──
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])

        hdr = self._table.horizontalHeader()
        for i, (_, w, stretch) in enumerate(COLUMNS):
            if stretch:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(i, w)

        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self._table)

        # ── Footer ──
        footer = QHBoxLayout()
        self._count_label = QLabel("0 dispositivos")
        self._count_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        footer.addWidget(self._count_label)
        footer.addStretch()

        btn_clear = QPushButton("Limpar Offline")
        btn_clear.clicked.connect(self._clear_offline)
        footer.addWidget(btn_clear)

        btn_refresh = QPushButton("Recarregar DB")
        btn_refresh.clicked.connect(self._load_from_db)
        footer.addWidget(btn_refresh)

        layout.addLayout(footer)

    def _load_from_db(self):
        self._devices.clear()
        for d in db.get_all_devices():
            self._devices[d["ip"]] = d
        self._refresh_table()

    def _start_scan(self):
        if self._scan_thread and self._scan_thread.isRunning():
            return
        self._btn_scan.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)
        self._progress_label.setText("Iniciando scan...")
        self.status_changed.emit("Scan em progresso...")
        db.add_log("INFO", "DISCOVERY", "Scan iniciado pelo usuario")

        self._scan_thread = ScanThread()
        self._scan_thread.device_found.connect(self._on_device_found)
        self._scan_thread.progress.connect(self._on_progress)
        self._scan_thread.scan_complete.connect(self._on_scan_complete)
        self._scan_thread.error.connect(self._on_scan_error)
        self._scan_thread.start()

    def _stop_scan(self):
        if self._scan_thread:
            self._scan_thread.stop()
        self._on_scan_complete(len(self._devices))

    def _on_device_found(self, device: dict):
        ip = device.get("ip", "")
        if not ip:
            return
        # Merge with existing
        existing = self._devices.get(ip, {})
        for k, v in device.items():
            if v:
                existing[k] = v
        existing["status"] = "online"
        self._devices[ip] = existing
        self._upsert_row(existing)
        self._update_count()

    def _on_progress(self, msg: str, current: int, total: int):
        self._progress_label.setText(msg)
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
        else:
            self._progress_bar.setRange(0, 0)
        self.scan_progress.emit(msg, current, total)

    def _on_scan_complete(self, count: int):
        self._btn_scan.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._progress_bar.setVisible(False)
        self._progress_label.setText(f"Scan concluido — {count} dispositivos encontrados")
        self.status_changed.emit(f"Scan concluido: {count} dispositivos")
        self.scan_finished.emit()
        self._scan_thread = None

    def _on_scan_error(self, msg: str):
        self._progress_label.setText(f"Erro: {msg}")
        self.status_changed.emit(f"Erro no scan: {msg}")
        self._on_scan_complete(len(self._devices))

    def _upsert_row(self, device: dict):
        ip = device.get("ip", "")
        # Find existing row
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 1)
            if item and item.text() == ip:
                self._fill_row(row, device)
                return
        # New row
        if self._filter and not self._matches_filter(device):
            return
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._fill_row(row, device)
        self._table.setRowHeight(row, 34)

    def _fill_row(self, row: int, d: dict):
        status = d.get("status", "offline")
        dot = QTableWidgetItem("●")
        dot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setForeground(QColor(C_SUCCESS if status == "online" else C_ERROR))
        dot.setToolTip(status.capitalize())
        self._table.setItem(row, 0, dot)

        self._table.setItem(row, 1,  QTableWidgetItem(d.get("ip", "")))
        self._table.setItem(row, 2,  QTableWidgetItem(d.get("mac", "")))
        self._table.setItem(row, 3,  QTableWidgetItem(d.get("vendor", "")))
        self._table.setItem(row, 4,  QTableWidgetItem(d.get("hostname", "")))
        self._table.setItem(row, 5,  QTableWidgetItem(d.get("model", "")))

        os_type = d.get("os_type", "unknown")
        os_item = QTableWidgetItem(os_type.capitalize())
        os_item.setForeground(QColor(OS_COLORS.get(os_type, C_TEXT_DIM)))
        self._table.setItem(row, 6, os_item)

        ssh_item = QTableWidgetItem("Sim" if d.get("ssh_open") else "")
        ssh_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if d.get("ssh_open"):
            ssh_item.setForeground(QColor(C_SUCCESS))
        self._table.setItem(row, 7, ssh_item)

        api_item = QTableWidgetItem("Sim" if d.get("api_open") else "")
        api_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if d.get("api_open"):
            api_item.setForeground(QColor(C_SUCCESS))
        self._table.setItem(row, 8, api_item)

        self._table.setItem(row, 9,  QTableWidgetItem(d.get("firmware", "")))
        self._table.setItem(row, 10, QTableWidgetItem(d.get("uptime", "")))

        last = (d.get("last_seen") or "").replace("T", " ")
        self._table.setItem(row, 11, QTableWidgetItem(last))

    def _refresh_table(self):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for d in self._devices.values():
            if self._filter and not self._matches_filter(d):
                continue
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._fill_row(row, d)
            self._table.setRowHeight(row, 34)
        self._table.setSortingEnabled(True)
        self._update_count()

    def _apply_filter(self, text: str):
        self._filter = text.strip().lower()
        self._refresh_table()

    def _matches_filter(self, d: dict) -> bool:
        f = self._filter
        return any(f in str(v).lower() for v in [
            d.get("ip"), d.get("mac"), d.get("hostname"),
            d.get("vendor"), d.get("model"), d.get("os_type")
        ])

    def _update_count(self):
        visible = self._table.rowCount()
        total = len(self._devices)
        if self._filter:
            self._count_label.setText(f"{visible} de {total} dispositivos")
        else:
            self._count_label.setText(f"{total} dispositivos")

    def _context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        ip_item = self._table.item(row, 1)
        if not ip_item:
            return
        ip = ip_item.text()
        device = self._devices.get(ip, {})

        menu = QMenu(self)

        action_info = QAction(f"IP: {ip}", self)
        action_info.setEnabled(False)
        menu.addAction(action_info)
        menu.addSeparator()

        action_copy = QAction("Copiar IP", self)
        action_copy.triggered.connect(lambda: self._copy_to_clipboard(ip))
        menu.addAction(action_copy)

        if device.get("mac"):
            action_copy_mac = QAction("Copiar MAC", self)
            action_copy_mac.triggered.connect(lambda: self._copy_to_clipboard(device["mac"]))
            menu.addAction(action_copy_mac)

        menu.addSeparator()

        os_type = device.get("os_type", "unknown")
        if os_type == "mikrotik":
            action_config = QAction("Abrir Auto Config (MikroTik)", self)
            action_config.triggered.connect(lambda: self._open_config(ip, "mikrotik"))
            menu.addAction(action_config)

        if os_type == "ubiquiti":
            action_config = QAction("Abrir Auto Config (Ubiquiti)", self)
            action_config.triggered.connect(lambda: self._open_config(ip, "ubiquiti"))
            menu.addAction(action_config)

        action_delete = QAction("Remover do banco", self)
        action_delete.triggered.connect(lambda: self._delete_device(ip))
        menu.addAction(action_delete)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _copy_to_clipboard(self, text: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def _open_config(self, ip: str, os_type: str):
        # Signal main window to navigate to auto_config with pre-filled IP
        parent = self.parent()
        while parent and not hasattr(parent, "_navigate"):
            parent = parent.parent()
        if parent and hasattr(parent, "_pages"):
            cfg_page = parent._pages.get("auto_config")
            if cfg_page and hasattr(cfg_page, "prefill"):
                cfg_page.prefill(ip, os_type)
            if hasattr(parent, "_navigate"):
                parent._navigate("auto_config")

    def _delete_device(self, ip: str):
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Remover {ip} do banco de dados?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_device(ip)
            self._devices.pop(ip, None)
            self._refresh_table()

    def _clear_offline(self):
        offline = [ip for ip, d in self._devices.items() if d.get("status") == "offline"]
        if not offline:
            QMessageBox.information(self, "Info", "Nenhum dispositivo offline encontrado.")
            return
        for ip in offline:
            db.delete_device(ip)
            del self._devices[ip]
        self._refresh_table()

    def on_activate(self):
        self._load_from_db()
