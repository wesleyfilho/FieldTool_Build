"""Templates page — manage, edit and apply configuration templates."""

import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTextEdit, QFrame,
    QSplitter, QComboBox, QLineEdit, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout,
)
from PySide6.QtCore import Qt

from app.templates.manager import get_templates, save_template, delete_template, export_template, import_template
from app.ui.styles import C_TEXT_DIM, C_SUCCESS, C_ERROR, C_MKTIK, C_UBNT


class TemplatesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._templates: list[dict] = []
        self._build_ui()
        self._load_templates()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Templates de Configuracao")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # ── Toolbar ──
        toolbar = QHBoxLayout()

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["Todos", "MikroTik", "Ubiquiti"])
        self._filter_combo.currentTextChanged.connect(self._apply_filter)
        toolbar.addWidget(QLabel("Filtrar:"))
        toolbar.addWidget(self._filter_combo)
        toolbar.addStretch()

        btn_new = QPushButton("  Novo Template")
        btn_new.setObjectName("btn_primary")
        btn_new.clicked.connect(self._new_template)
        toolbar.addWidget(btn_new)

        btn_import = QPushButton("  Importar")
        btn_import.clicked.connect(self._import_template)
        toolbar.addWidget(btn_import)

        layout.addLayout(toolbar)

        # ── Splitter: list | editor ──
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: template list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_template_selected)
        left_layout.addWidget(self._list)

        list_btns = QHBoxLayout()
        self._btn_delete = QPushButton("Remover")
        self._btn_delete.setObjectName("btn_danger")
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_delete.setEnabled(False)

        self._btn_export = QPushButton("Exportar")
        self._btn_export.clicked.connect(self._export_selected)
        self._btn_export.setEnabled(False)

        list_btns.addWidget(self._btn_delete)
        list_btns.addWidget(self._btn_export)
        left_layout.addLayout(list_btns)
        splitter.addWidget(left)

        # Right: editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        editor_title = QLabel("Editor de Template")
        editor_title.setObjectName("section_title")
        right_layout.addWidget(editor_title)

        form_group = QGroupBox("Informacoes")
        form = QFormLayout(form_group)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Nome do template")
        form.addRow("Nome:", self._name_input)

        self._devtype_combo = QComboBox()
        self._devtype_combo.addItems(["mikrotik", "ubiquiti"])
        form.addRow("Dispositivo:", self._devtype_combo)

        self._cfgtype_combo = QComboBox()
        self._cfgtype_combo.addItems(["ap", "client", "bridge", "repeater"])
        form.addRow("Tipo:", self._cfgtype_combo)

        right_layout.addWidget(form_group)

        params_label = QLabel("Parametros (JSON):")
        params_label.setStyleSheet(f"color: {C_TEXT_DIM}; margin-top: 8px;")
        right_layout.addWidget(params_label)

        self._params_edit = QTextEdit()
        self._params_edit.setPlaceholderText('{\n  "ssid": "MinhaRede",\n  "password": "senha123"\n}')
        self._params_edit.setFontFamily("Consolas")
        right_layout.addWidget(self._params_edit)

        editor_btns = QHBoxLayout()
        editor_btns.addStretch()

        self._btn_save = QPushButton("  Salvar Template")
        self._btn_save.setObjectName("btn_success")
        self._btn_save.clicked.connect(self._save_template)
        editor_btns.addWidget(self._btn_save)

        right_layout.addLayout(editor_btns)
        splitter.addWidget(right)

        splitter.setSizes([300, 600])
        layout.addWidget(splitter)

        # ── Status ──
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        layout.addWidget(self._status)

    def _load_templates(self):
        self._templates = get_templates()
        self._apply_filter(self._filter_combo.currentText())

    def _apply_filter(self, text: str):
        self._list.clear()
        filter_type = "" if text == "Todos" else text.lower()
        for t in self._templates:
            if filter_type and t.get("device_type", "").lower() != filter_type:
                continue
            item = QListWidgetItem()
            dtype = t.get("device_type", "")
            ctype = t.get("config_type", "")
            display = f"{t.get('name', '?')}  [{dtype.upper()} / {ctype}]"
            item.setText(display)
            item.setData(Qt.ItemDataRole.UserRole, t.get("name"))
            color = C_MKTIK if dtype == "mikrotik" else C_UBNT
            from PySide6.QtGui import QColor
            item.setForeground(QColor(color))
            self._list.addItem(item)

    def _on_template_selected(self, current, previous):
        if not current:
            self._btn_delete.setEnabled(False)
            self._btn_export.setEnabled(False)
            return
        self._btn_delete.setEnabled(True)
        self._btn_export.setEnabled(True)
        name = current.data(Qt.ItemDataRole.UserRole)
        t = next((x for x in self._templates if x.get("name") == name), None)
        if not t:
            return
        self._name_input.setText(t.get("name", ""))
        dtype = t.get("device_type", "mikrotik")
        self._devtype_combo.setCurrentText(dtype)
        ctype = t.get("config_type", "ap")
        self._cfgtype_combo.setCurrentText(ctype)
        params = t.get("params", {})
        self._params_edit.setPlainText(json.dumps(params, indent=2, ensure_ascii=False))

    def _new_template(self):
        self._list.clearSelection()
        self._name_input.clear()
        self._params_edit.clear()
        self._devtype_combo.setCurrentIndex(0)
        self._cfgtype_combo.setCurrentIndex(0)
        self._name_input.setFocus()

    def _save_template(self):
        name = self._name_input.text().strip()
        if not name:
            self._status.setText("Informe um nome para o template.")
            return
        try:
            params = json.loads(self._params_edit.toPlainText() or "{}")
        except json.JSONDecodeError as e:
            self._status.setText(f"JSON invalido: {e}")
            return

        dtype = self._devtype_combo.currentText()
        ctype = self._cfgtype_combo.currentText()
        if save_template(name, dtype, ctype, params):
            self._status.setText(f"Template '{name}' salvo com sucesso.")
            self._load_templates()
        else:
            self._status.setText("Erro ao salvar template.")

    def _delete_selected(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "Confirmar", f"Remover template '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_template(name)
            self._load_templates()
            self._new_template()

    def _export_selected(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Template", f"{name}.json", "JSON (*.json)"
        )
        if path:
            if export_template(name, path):
                self._status.setText(f"Template exportado: {path}")
            else:
                self._status.setText("Erro ao exportar template.")

    def _import_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar Template", "", "JSON (*.json)"
        )
        if path:
            ok, result = import_template(path)
            if ok:
                self._status.setText(f"Template '{result}' importado com sucesso.")
                self._load_templates()
            else:
                self._status.setText(f"Erro ao importar: {result}")

    def on_activate(self):
        self._load_templates()
