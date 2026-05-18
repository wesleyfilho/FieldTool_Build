"""Dashboard page — summary stats and recent devices."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QToolTip,
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QCursor

from app.database import db
from app.ui.styles import OS_COLORS, STATUS_COLORS, C_SUCCESS, C_ERROR, C_MKTIK, C_UBNT, C_WARNING, C_LOCAL, C_TEXT_DIM


def _stat_card(value: str, label: str, color: str = "#388bfd") -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    card.setMinimumWidth(140)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(4)

    val_lbl = QLabel(value)
    val_lbl.setObjectName("stat_value")
    val_lbl.setStyleSheet(f"color: {color}; font-size: 30px; font-weight: bold;")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

    lbl = QLabel(label)
    lbl.setObjectName("stat_label")
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

    layout.addWidget(val_lbl)
    layout.addWidget(lbl)
    return card


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()
        # Auto-refresh every 30s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Dashboard")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # ── Stat cards ──
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self._card_total  = _stat_card("0", "Total Dispositivos", "#388bfd")
        self._card_online = _stat_card("0", "Online",             C_SUCCESS)
        self._card_mktik  = _stat_card("0", "MikroTik",           C_MKTIK)
        self._card_ubnt   = _stat_card("0", "Ubiquiti",           C_UBNT)
        self._card_ssh    = _stat_card("0", "SSH Aberto",          "#a371f7")
        cards_row.addWidget(self._card_total)
        cards_row.addWidget(self._card_online)
        cards_row.addWidget(self._card_mktik)
        cards_row.addWidget(self._card_ubnt)
        cards_row.addWidget(self._card_ssh)
        cards_row.addStretch()
        layout.addLayout(cards_row)

        # ── Recent devices table ──
        sec_label = QLabel("Dispositivos Recentes")
        sec_label.setObjectName("section_title")
        layout.addWidget(sec_label)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Status", "IP", "Hostname", "Fabricante", "Modelo", "Tipo", "Visto"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 70)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.setSortingEnabled(True)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.itemEntered.connect(self._on_item_hover)
        self._table.setMouseTracking(True)
        layout.addWidget(self._table)

        hint = QLabel("Clique no IP para abrir no navegador")
        hint.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(hint)

    def refresh(self):
        devices = db.get_all_devices()
        total   = len(devices)
        online  = sum(1 for d in devices if d.get("status") == "online")
        mktik   = sum(1 for d in devices if d.get("os_type") == "mikrotik")
        ubnt    = sum(1 for d in devices if d.get("os_type") == "ubiquiti")
        ssh     = sum(1 for d in devices if d.get("ssh_open"))

        self._card_total.findChild(QLabel, "stat_value")
        self._update_card(self._card_total,  str(total))
        self._update_card(self._card_online, str(online))
        self._update_card(self._card_mktik,  str(mktik))
        self._update_card(self._card_ubnt,   str(ubnt))
        self._update_card(self._card_ssh,    str(ssh))

        self._fill_table(devices[:50])

    def _update_card(self, card: QFrame, value: str):
        for child in card.findChildren(QLabel):
            if child.objectName() == "stat_value":
                child.setText(value)
                break

    def _fill_table(self, devices: list[dict]):
        self._table.setRowCount(0)
        for d in devices:
            row = self._table.rowCount()
            self._table.insertRow(row)

            status = d.get("status", "offline")
            status_item = QTableWidgetItem("● " + status.capitalize())
            status_item.setForeground(QColor(C_SUCCESS if status == "online" else C_ERROR))
            self._table.setItem(row, 0, status_item)

            ip_item = QTableWidgetItem(d.get("ip", ""))
            ip_item.setForeground(QColor("#388bfd"))
            ip_item.setToolTip(f"Abrir http://{d.get('ip','')} no navegador")
            self._table.setItem(row, 1, ip_item)
            self._table.setItem(row, 2, QTableWidgetItem(d.get("hostname", "")))
            self._table.setItem(row, 3, QTableWidgetItem(d.get("vendor", "")))
            self._table.setItem(row, 4, QTableWidgetItem(d.get("model", "")))

            os_type = d.get("os_type", "unknown")
            os_item = QTableWidgetItem(os_type.capitalize())
            os_item.setForeground(QColor(OS_COLORS.get(os_type, "#8b949e")))
            self._table.setItem(row, 5, os_item)

            last_seen = d.get("last_seen", "")
            if last_seen:
                last_seen = last_seen.replace("T", " ")
            self._table.setItem(row, 6, QTableWidgetItem(last_seen))

            self._table.setRowHeight(row, 34)

    def _on_cell_clicked(self, row: int, col: int):
        if col != 1:
            return
        item = self._table.item(row, col)
        if not item:
            return
        ip = item.text()
        if ip:
            QDesktopServices.openUrl(QUrl(f"http://{ip}"))

    def _on_item_hover(self, item):
        if item and item.column() == 1:
            self._table.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._table.setCursor(Qt.CursorShape.ArrowCursor)

    def on_activate(self):
        self.refresh()
