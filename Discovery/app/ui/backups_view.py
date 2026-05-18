"""Backups page — store and manage device configuration backups."""

import re
import json
import shutil
import tarfile
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QDialog, QFormLayout, QComboBox, QPlainTextEdit,
    QFileDialog, QMessageBox, QDialogButtonBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.database import db
from app.core.config import config
from app.ui.styles import C_TEXT_DIM, C_MKTIK, C_UBNT, C_SUCCESS, C_ERROR, C_WARNING


# ── Helpers ──────────────────────────────────────────────────────────────────

def _backups_dir() -> Path:
    d = Path(config.get("backups_path", "config/backups"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ext(device_type: str) -> str:
    return ".rsc" if device_type == "mikrotik" else ".cfg"


def _detect_type(content: str) -> str:
    """Guess device type from config content."""
    # MikroTik RouterOS export — lines start with RouterOS path commands
    if re.search(r"# RouterOS", content, re.IGNORECASE):
        return "mikrotik"
    if re.search(r"^/(ip|interface|system|routing|queue|firewall|mpls|caps-man)\b",
                 content, re.MULTILINE):
        return "mikrotik"
    # Ubiquiti airOS flat-key config  (key.subkey=value)
    if re.search(r"\bwireless\.\d+\.\w+=|\bnetmode=|\bairos\b|\bairmax\b|\bUBNT\b",
                 content, re.IGNORECASE):
        return "ubiquiti"
    # Ubiquiti JSON backup
    try:
        data = json.loads(content)
        if isinstance(data, dict) and any(
            k in data for k in ("wireless", "netmode", "system", "network", "unifi")
        ):
            return "ubiquiti"
    except Exception:
        pass
    return ""


def _fmt_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024*1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _read_backup_file(path: Path) -> tuple[str, str]:
    """
    Lê um arquivo de backup, lidando com os formatos reais das antenas.
    Retorna (conteudo_texto, tipo_detectado_hint).

    Formatos suportados:
      MikroTik: .rsc .txt (texto) — .backup é binário e NÃO pode ser lido
      Ubiquiti: system.cfg .cfg .txt (texto) — .unf e .tar.gz são archives
                 com system.cfg dentro
    """
    suffix = path.suffix.lower()
    name_lower = path.name.lower()

    # Ubiquiti archive: .unf (firmware novo) ou .tar.gz / .tar
    is_archive = (
        suffix in (".unf", ".tar", ".gz")
        or name_lower.endswith(".tar.gz")
    )
    if is_archive:
        try:
            with tarfile.open(str(path), "r:*") as tar:
                members = tar.getmembers()
                # Prioridade: system.cfg, depois running.cfg, depois qualquer .cfg
                priority = ["system.cfg", "running.cfg"]
                target = None
                for pname in priority:
                    target = next(
                        (m for m in members if m.name.endswith(pname) and m.isfile()),
                        None,
                    )
                    if target:
                        break
                if not target:
                    target = next(
                        (m for m in members if m.name.endswith(".cfg") and m.isfile()),
                        None,
                    )
                if target:
                    f = tar.extractfile(target)
                    if f:
                        content = f.read().decode("utf-8", errors="replace")
                        return content, "ubiquiti"

                names = [m.name for m in members[:15]]
                raise ValueError(
                    f"Nenhum arquivo .cfg encontrado dentro do backup.\n"
                    f"Conteudo do arquivo: {', '.join(names)}"
                )
        except tarfile.TarError as e:
            raise ValueError(f"Nao foi possivel abrir o arquivo comprimido:\n{e}")

    # MikroTik .backup é binário — orientar o usuario
    if suffix == ".backup":
        raise ValueError(
            "Arquivos .backup do MikroTik sao binarios e nao podem ser lidos como texto.\n\n"
            "Para exportar uma config legivel no MikroTik:\n"
            "  Winbox > New Terminal > /export\n"
            "  ou: /export file=backup  (gera um .rsc no Files)"
        )

    # Texto puro: .rsc .cfg .txt .json e outros
    try:
        return path.read_text(encoding="utf-8", errors="replace"), ""
    except Exception as e:
        raise ValueError(f"Nao foi possivel ler o arquivo:\n{e}")


# ── Novo Backup Dialog ────────────────────────────────────────────────────────

class _NewBackupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo Backup")
        self.setMinimumWidth(660)
        self.setMinimumHeight(540)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._name = QLineEdit()
        self._name.setPlaceholderText("Ex: Antena-UBNT-Telhado ou MK-AP-Matriz")
        form.addRow("Nome *:", self._name)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["Auto-detectar", "MikroTik", "Ubiquiti"])
        form.addRow("Tipo:", self._type_combo)

        self._ip = QLineEdit()
        self._ip.setPlaceholderText("192.168.1.1  (opcional)")
        form.addRow("IP do dispositivo:", self._ip)

        self._mac = QLineEdit()
        self._mac.setPlaceholderText("AA:BB:CC:DD:EE:FF  (opcional)")
        form.addRow("MAC:", self._mac)

        self._notes = QLineEdit()
        self._notes.setPlaceholderText("Localizacao, cliente, observacoes...")
        form.addRow("Notas:", self._notes)

        layout.addLayout(form)

        # Config text area header
        cfg_header = QHBoxLayout()
        cfg_lbl = QLabel("Configuracao *:")
        cfg_header.addWidget(cfg_lbl)
        cfg_header.addStretch()

        self._detect_lbl = QLabel("")
        self._detect_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        cfg_header.addWidget(self._detect_lbl)

        btn_import = QPushButton("Importar Arquivo")
        btn_import.clicked.connect(self._import_file)
        cfg_header.addWidget(btn_import)
        layout.addLayout(cfg_header)

        self._config_text = QPlainTextEdit()
        self._config_text.setFont(QFont("Consolas", 9))
        self._config_text.setPlaceholderText(
            "Cole aqui o backup de configuracao...\n\n"
            "MikroTik: Winbox > New Terminal > /export\n"
            "Ubiquiti: More > Config > Download (system.cfg)\n"
            "           ou acesse /etc/persistent/cfg/ via SSH"
        )
        self._config_text.setMinimumHeight(220)
        self._config_text.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._config_text)

        # Dialog buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText("Salvar Backup")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_text_changed(self):
        content = self._config_text.toPlainText()
        if len(content) < 10:
            self._detect_lbl.setText("")
            return
        detected = _detect_type(content)
        if detected == "mikrotik":
            self._detect_lbl.setText(f'<span style="color:{C_MKTIK}">Detectado: MikroTik RouterOS</span>')
        elif detected == "ubiquiti":
            self._detect_lbl.setText(f'<span style="color:{C_UBNT}">Detectado: Ubiquiti airOS</span>')
        else:
            self._detect_lbl.setText(
                f'<span style="color:{C_WARNING}">Tipo nao reconhecido — selecione manualmente</span>'
            )
        self._detect_lbl.setTextFormat(Qt.TextFormat.RichText)

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar configuracao",
            "",
            "Backups de antenas (*.rsc *.cfg *.txt *.json *.unf *.tar *.gz);;"
            "MikroTik export (*.rsc *.txt);;"
            "Ubiquiti config/backup (*.cfg *.unf *.tar *.gz);;"
            "Todos os arquivos (*.*)"
        )
        if not path:
            return
        try:
            content, type_hint = _read_backup_file(Path(path))
            self._config_text.setPlainText(content)
            if not self._name.text().strip():
                self._name.setText(Path(path).stem)
            # Se o arquivo já indicou o tipo (ex: .unf → ubiquiti), aplica no combo
            if type_hint == "ubiquiti" and self._type_combo.currentIndex() == 0:
                self._type_combo.setCurrentText("Ubiquiti")
        except ValueError as e:
            QMessageBox.warning(self, "Formato nao suportado", str(e))
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))

    def _save(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Aviso", "Informe um nome para o backup.")
            return
        content = self._config_text.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Aviso", "Cole ou importe a configuracao antes de salvar.")
            return

        combo = self._type_combo.currentText()
        if combo == "Auto-detectar":
            device_type = _detect_type(content) or "desconhecido"
        else:
            device_type = combo.lower()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^\w\-]", "_", name)
        filename = f"{safe_name}_{timestamp}{_ext(device_type)}"

        dest = _backups_dir() / filename
        try:
            dest.write_text(content, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Nao foi possivel salvar o arquivo:\n{e}")
            return

        db.save_backup(
            name=name,
            device_type=device_type,
            filename=filename,
            device_ip=self._ip.text().strip(),
            device_mac=self._mac.text().strip(),
            notes=self._notes.text().strip(),
            file_size=dest.stat().st_size,
        )
        self.accept()


# ── Ver Backup Dialog ─────────────────────────────────────────────────────────

class _ViewDialog(QDialog):
    def __init__(self, backup: dict, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Backup: {backup.get('name', '')}")
        self.setMinimumWidth(720)
        self.setMinimumHeight(540)
        self._build(backup, content)

    def _build(self, b: dict, content: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Info row
        dt = b.get("device_type", "")
        color = C_MKTIK if dt == "mikrotik" else C_UBNT if dt == "ubiquiti" else C_TEXT_DIM
        info = QLabel(
            f'<span style="color:{color};font-weight:bold">{dt.capitalize()}</span>'
            f'  |  IP: {b.get("device_ip") or "—"}'
            f'  |  MAC: {b.get("device_mac") or "—"}'
            f'  |  {(b.get("created_at") or "").replace("T"," ")[:16]}'
            f'  |  {_fmt_size(b.get("file_size", 0))}'
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 12px;")
        layout.addWidget(info)

        if b.get("notes"):
            notes_lbl = QLabel(f"Notas: {b['notes']}")
            notes_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
            layout.addWidget(notes_lbl)

        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont("Consolas", 9))
        txt.setPlainText(content)
        layout.addWidget(txt)

        close_btn = QPushButton("Fechar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


# ── Backups Page ──────────────────────────────────────────────────────────────

COLS = [
    ("Nome",     200, True),
    ("Tipo",     90,  False),
    ("IP",       120, False),
    ("MAC",      140, False),
    ("Notas",    180, True),
    ("Data",     140, False),
    ("Tamanho",  80,  False),
]


class BackupsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._backups: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Backups de Configuracao")
        title.setObjectName("page_title")
        layout.addWidget(title)

        sub = QLabel("Salve e organize os backups das suas antenas MikroTik e Ubiquiti")
        sub.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(sub)

        # Header
        hdr = QHBoxLayout()
        self._btn_new = QPushButton("  Novo Backup")
        self._btn_new.setObjectName("btn_primary")
        self._btn_new.setMinimumHeight(36)
        self._btn_new.clicked.connect(self._new_backup)
        hdr.addWidget(self._btn_new)
        hdr.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar por nome, IP, tipo, notas...")
        self._search.setMinimumWidth(260)
        self._search.textChanged.connect(self._refresh_table)
        hdr.addWidget(self._search)
        layout.addLayout(hdr)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLS))
        self._table.setHorizontalHeaderLabels([c[0] for c in COLS])
        hh = self._table.horizontalHeader()
        for i, (_, w, stretch) in enumerate(COLS):
            if stretch:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(i, w)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._view_selected)
        layout.addWidget(self._table)

        # Footer
        footer = QHBoxLayout()
        self._count_lbl = QLabel("0 backups")
        self._count_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")

        dir_lbl = QLabel("")
        dir_lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 10px;")
        try:
            dir_lbl.setText(f"Pasta: {_backups_dir()}")
        except Exception:
            pass

        footer.addWidget(self._count_lbl)
        footer.addWidget(dir_lbl, 1)

        btn_view = QPushButton("Ver Config")
        btn_view.clicked.connect(self._view_selected)
        footer.addWidget(btn_view)

        btn_export = QPushButton("Exportar")
        btn_export.clicked.connect(self._export_selected)
        footer.addWidget(btn_export)

        btn_del = QPushButton("Remover")
        btn_del.setObjectName("btn_danger")
        btn_del.clicked.connect(self._delete_selected)
        footer.addWidget(btn_del)

        layout.addLayout(footer)

    # ── Data ─────────────────────────────────────────────────────────────────

    def _load(self):
        self._backups = db.get_backups()
        self._refresh_table()

    def _refresh_table(self):
        f = self._search.text().strip().lower()
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for b in self._backups:
            if f and not any(
                f in str(b.get(k, "")).lower()
                for k in ("name", "device_type", "device_ip", "device_mac", "notes")
            ):
                continue

            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setRowHeight(row, 34)

            name_item = QTableWidgetItem(b.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, b["id"])
            self._table.setItem(row, 0, name_item)

            dt = b.get("device_type", "")
            dt_item = QTableWidgetItem(dt.capitalize())
            color = C_MKTIK if dt == "mikrotik" else C_UBNT if dt == "ubiquiti" else C_TEXT_DIM
            dt_item.setForeground(QColor(color))
            self._table.setItem(row, 1, dt_item)

            self._table.setItem(row, 2, QTableWidgetItem(b.get("device_ip", "")))
            self._table.setItem(row, 3, QTableWidgetItem(b.get("device_mac", "")))
            self._table.setItem(row, 4, QTableWidgetItem(b.get("notes", "")))

            created = (b.get("created_at") or "").replace("T", " ")[:16]
            self._table.setItem(row, 5, QTableWidgetItem(created))

            size_item = QTableWidgetItem(_fmt_size(b.get("file_size", 0)))
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 6, size_item)

        self._table.setSortingEnabled(True)
        visible = self._table.rowCount()
        total = len(self._backups)
        self._count_lbl.setText(
            f"{visible} de {total} backup(s)" if f else f"{total} backup(s)"
        )

    def _selected_backup(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if not item:
            return None
        backup_id = item.data(Qt.ItemDataRole.UserRole)
        return next((b for b in self._backups if b["id"] == backup_id), None)

    def _read_file(self, b: dict) -> str | None:
        path = _backups_dir() / b.get("filename", "")
        if not path.exists():
            QMessageBox.warning(self, "Aviso", f"Arquivo nao encontrado:\n{path}")
            return None
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            QMessageBox.warning(self, "Erro", str(e))
            return None

    # ── Actions ──────────────────────────────────────────────────────────────

    def _new_backup(self):
        dlg = _NewBackupDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load()

    def _view_selected(self):
        b = self._selected_backup()
        if not b:
            return
        content = self._read_file(b)
        if content is None:
            return
        _ViewDialog(b, content, self).exec()

    def _export_selected(self):
        b = self._selected_backup()
        if not b:
            return
        src = _backups_dir() / b.get("filename", "")
        if not src.exists():
            QMessageBox.warning(self, "Aviso", "Arquivo nao encontrado.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Exportar backup", b.get("filename", "backup"),
            "Todos os arquivos (*.*)"
        )
        if dest:
            shutil.copy2(str(src), dest)
            QMessageBox.information(self, "Exportado", f"Backup salvo em:\n{dest}")

    def _delete_selected(self):
        b = self._selected_backup()
        if not b:
            return
        reply = QMessageBox.question(
            self, "Confirmar remocao",
            f"Remover o backup '{b.get('name')}'?\nO arquivo tambem sera deletado do disco.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        path = _backups_dir() / b.get("filename", "")
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        db.delete_backup(b["id"])
        self._load()

    def on_activate(self):
        self._load()
