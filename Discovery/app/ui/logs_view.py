"""Logs page — filterable system log viewer."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from app.database import db
from app.ui.styles import LOG_COLORS, C_TEXT_DIM


class LogsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(15_000)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Logs do Sistema")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # ── Toolbar ──
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Nivel:"))
        self._level_combo = QComboBox()
        self._level_combo.addItems(["Todos", "INFO", "SUCCESS", "WARNING", "ERROR"])
        self._level_combo.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self._level_combo)

        toolbar.addWidget(QLabel("Categoria:"))
        self._cat_combo = QComboBox()
        self._cat_combo.addItems(["Todos", "DISCOVERY", "CONFIG", "AUTH", "SYSTEM"])
        self._cat_combo.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self._cat_combo)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filtrar por mensagem ou IP...")
        self._search.setMinimumWidth(200)
        self._search.textChanged.connect(self._apply_text_filter)
        toolbar.addWidget(self._search, 1)

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(btn_refresh)

        btn_clear = QPushButton("Limpar Logs")
        btn_clear.setObjectName("btn_danger")
        btn_clear.clicked.connect(self._clear_logs)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        # ── Table ──
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Timestamp", "Nivel", "Categoria", "Dispositivo", "Mensagem"])

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 150)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 80)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 100)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(3, 120)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(False)
        layout.addWidget(self._table)

        # Footer
        footer = QHBoxLayout()
        self._count_label = QLabel("0 registros")
        self._count_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        footer.addWidget(self._count_label)
        footer.addStretch()
        layout.addLayout(footer)

        self._all_logs: list[dict] = []

    def refresh(self):
        level = self._level_combo.currentText()
        cat   = self._cat_combo.currentText()
        self._all_logs = db.get_logs(
            limit=1000,
            level=level if level != "Todos" else "",
            category=cat if cat != "Todos" else "",
        )
        self._apply_text_filter(self._search.text())

    def _apply_text_filter(self, text: str):
        flt = text.strip().lower()
        logs = self._all_logs
        if flt:
            logs = [l for l in logs if
                    flt in l.get("message", "").lower() or
                    flt in l.get("device_ip", "").lower()]
        self._fill_table(logs)

    def _fill_table(self, logs: list[dict]):
        self._table.setRowCount(0)
        for log in logs:
            row = self._table.rowCount()
            self._table.insertRow(row)

            ts = (log.get("timestamp") or "").replace("T", " ")
            self._table.setItem(row, 0, QTableWidgetItem(ts))

            level = log.get("level", "")
            level_item = QTableWidgetItem(level)
            color = LOG_COLORS.get(level, "#e6edf3")
            level_item.setForeground(QColor(color))
            level_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 1, level_item)

            self._table.setItem(row, 2, QTableWidgetItem(log.get("category", "")))
            self._table.setItem(row, 3, QTableWidgetItem(log.get("device_ip", "")))
            self._table.setItem(row, 4, QTableWidgetItem(log.get("message", "")))

            self._table.setRowHeight(row, 30)

        self._count_label.setText(f"{self._table.rowCount()} registros")

    def _clear_logs(self):
        reply = QMessageBox.question(
            self, "Confirmar", "Limpar todos os logs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.clear_logs()
            self.refresh()

    def on_activate(self):
        self.refresh()
