"""Updates page — check and apply updates from GitHub Releases."""

import re
import sys
import json
import subprocess
import threading
import urllib.request
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QProgressBar, QTextEdit, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from app.version import VERSION
from app.core.config import config
from app.ui.styles import C_SUCCESS, C_ERROR, C_TEXT_DIM, C_WARNING, C_ACCENT2


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_ver(v: str) -> tuple:
    """'v1.2.3' → (1, 2, 3)"""
    clean = re.sub(r"[^\d.]", "", v)
    parts = [x for x in clean.split(".") if x]
    try:
        return tuple(int(x) for x in parts)
    except Exception:
        return (0,)


def _is_newer(remote: str, local: str = VERSION) -> bool:
    return _parse_ver(remote) > _parse_ver(local)


def _exe_dir() -> Path:
    """Directory where the app exe lives (frozen) or project root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _fetch_release(repo: str) -> dict:
    """Call GitHub API and return the latest release dict."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url, headers={"User-Agent": "FieldTool-Updater/1.0", "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _find_exe_asset(assets: list) -> dict | None:
    """Return the first .exe asset from the release."""
    for a in assets:
        if a.get("name", "").lower().endswith(".exe"):
            return a
    return None


def _download(url: str, dest: Path, progress_cb) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "FieldTool-Updater/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                progress_cb(done, total)


def _write_updater(app_dir: Path, new_exe: Path, exe_name: str) -> Path:
    """Write updater.bat that replaces the exe and restarts after the app closes."""
    bat = app_dir / "updater.bat"
    bat.write_text(
        f'@echo off\n'
        f'timeout /t 3 /nobreak > nul\n'
        f'del /f /q "{exe_name}"\n'
        f'ren "{new_exe.name}" "{exe_name}"\n'
        f'start "" "{exe_name}"\n'
        f'del /f /q "%~f0"\n',
        encoding="utf-8",
    )
    return bat


# ── Updates Page ──────────────────────────────────────────────────────────────

class UpdatesPage(QWidget):
    _log_sig      = Signal(str, str)   # message, color
    _progress_sig = Signal(int, int)   # done, total
    _state_sig    = Signal(str)        # "idle" | "checking" | "ready" | "downloading" | "done"
    _release_sig  = Signal(dict)       # release info dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._latest_release: dict = {}
        self._log_sig.connect(self._append_log)
        self._progress_sig.connect(self._update_progress)
        self._state_sig.connect(self._apply_state)
        self._release_sig.connect(self._show_release)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Atualizacoes")
        title.setObjectName("page_title")
        layout.addWidget(title)

        sub = QLabel("Verifique e instale atualizacoes do FieldTool via GitHub Releases")
        sub.setStyleSheet(f"color: {C_TEXT_DIM};")
        layout.addWidget(sub)

        # ── GitHub repo config ──
        repo_frame = QFrame()
        repo_frame.setObjectName("card")
        repo_layout = QHBoxLayout(repo_frame)
        repo_layout.setContentsMargins(16, 12, 16, 12)

        repo_lbl = QLabel("Repositorio GitHub:")
        repo_lbl.setStyleSheet(f"color: {C_TEXT_DIM};")
        repo_layout.addWidget(repo_lbl)

        self._repo_input = QLineEdit()
        self._repo_input.setPlaceholderText("usuario/fieldtool")
        self._repo_input.setText(config.get("github_repo", ""))
        self._repo_input.setMinimumWidth(240)
        repo_layout.addWidget(self._repo_input, 1)

        btn_save_repo = QPushButton("Salvar")
        btn_save_repo.clicked.connect(self._save_repo)
        repo_layout.addWidget(btn_save_repo)

        layout.addWidget(repo_frame)

        # ── Version info card ──
        info_frame = QFrame()
        info_frame.setObjectName("card")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(6)

        row_cur = QHBoxLayout()
        row_cur.addWidget(QLabel("Versao atual:"))
        self._lbl_current = QLabel(f"v{VERSION}")
        self._lbl_current.setStyleSheet(f"color: {C_ACCENT2}; font-weight: bold;")
        row_cur.addWidget(self._lbl_current)
        row_cur.addStretch()
        info_layout.addLayout(row_cur)

        row_lat = QHBoxLayout()
        row_lat.addWidget(QLabel("Ultima versao:"))
        self._lbl_latest = QLabel("—")
        self._lbl_latest.setStyleSheet(f"color: {C_TEXT_DIM};")
        row_lat.addWidget(self._lbl_latest)
        row_lat.addStretch()
        info_layout.addLayout(row_lat)

        row_status = QHBoxLayout()
        row_status.addWidget(QLabel("Status:"))
        self._lbl_status = QLabel("Nao verificado")
        self._lbl_status.setStyleSheet(f"color: {C_TEXT_DIM};")
        row_status.addWidget(self._lbl_status)
        row_status.addStretch()
        info_layout.addLayout(row_status)

        layout.addWidget(info_frame)

        # ── Release notes (hidden until update found) ──
        self._notes_frame = QFrame()
        self._notes_frame.setObjectName("card")
        self._notes_frame.setVisible(False)
        notes_layout = QVBoxLayout(self._notes_frame)
        notes_layout.setContentsMargins(16, 12, 16, 12)

        self._notes_title = QLabel("")
        self._notes_title.setObjectName("section_title")
        notes_layout.addWidget(self._notes_title)

        self._notes_text = QTextEdit()
        self._notes_text.setReadOnly(True)
        self._notes_text.setMaximumHeight(120)
        notes_layout.addWidget(self._notes_text)

        layout.addWidget(self._notes_frame)

        # ── Progress bar ──
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(8)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # ── Action buttons ──
        btn_row = QHBoxLayout()

        self._btn_check = QPushButton("  Verificar Atualizacoes")
        self._btn_check.setObjectName("btn_primary")
        self._btn_check.setMinimumHeight(40)
        self._btn_check.setMinimumWidth(200)
        self._btn_check.clicked.connect(self._check_update)
        btn_row.addWidget(self._btn_check)

        self._btn_update = QPushButton("  Baixar e Instalar")
        self._btn_update.setObjectName("btn_success")
        self._btn_update.setMinimumHeight(40)
        self._btn_update.setMinimumWidth(180)
        self._btn_update.setVisible(False)
        self._btn_update.clicked.connect(self._apply_update)
        btn_row.addWidget(self._btn_update)

        btn_row.addStretch()

        self._btn_github = QPushButton("  Abrir no GitHub")
        self._btn_github.setVisible(False)
        self._btn_github.clicked.connect(self._open_github)
        btn_row.addWidget(self._btn_github)

        layout.addLayout(btn_row)

        # ── Log ──
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        self._log.setPlaceholderText("Log de atualizacoes...")
        layout.addWidget(self._log)

        layout.addStretch()

    # ── Repo save ─────────────────────────────────────────────────────────────

    def _save_repo(self):
        repo = self._repo_input.text().strip()
        if repo and "/" not in repo:
            QMessageBox.warning(self, "Aviso", "Formato invalido. Use: usuario/nome-repo")
            return
        config.set("github_repo", repo)
        self._log_sig.emit(f"Repositorio salvo: {repo}", C_SUCCESS)

    # ── Check update ──────────────────────────────────────────────────────────

    def _check_update(self):
        repo = self._repo_input.text().strip()
        if not repo:
            QMessageBox.warning(self, "Aviso",
                "Configure o repositorio GitHub antes de verificar.\n"
                "Formato: usuario/nome-do-repo")
            return
        config.set("github_repo", repo)
        self._state_sig.emit("checking")
        self._log_sig.emit(f"Verificando atualizacoes em github.com/{repo}...", "")

        def _run():
            try:
                release = _fetch_release(repo)
                self._release_sig.emit(release)
            except Exception as e:
                self._log_sig.emit(f"Erro ao verificar: {e}", C_ERROR)
                self._state_sig.emit("idle")

        threading.Thread(target=_run, daemon=True).start()

    # ── Apply update ──────────────────────────────────────────────────────────

    def _apply_update(self):
        if not self._latest_release:
            return

        asset = _find_exe_asset(self._latest_release.get("assets", []))
        if not asset:
            QMessageBox.warning(self, "Aviso",
                "Nenhum arquivo .exe encontrado neste release.\n"
                "Verifique os assets publicados no GitHub.")
            return

        if not getattr(sys, "frozen", False):
            QMessageBox.information(self, "Modo desenvolvimento",
                "Atualizacao automatica funciona apenas no executavel compilado.\n"
                "Baixe o novo FieldTool.exe manualmente no GitHub Releases.")
            self._open_github()
            return

        tag = self._latest_release.get("tag_name", "nova")
        reply = QMessageBox.question(
            self, "Confirmar atualizacao",
            f"Instalar FieldTool {tag}?\n\n"
            f"O programa sera reiniciado automaticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._state_sig.emit("downloading")
        url = asset["browser_download_url"]
        exe_dir = _exe_dir()
        dest = exe_dir / "FieldTool_update.exe"

        self._log_sig.emit(f"Baixando {asset['name']} ({asset['size'] // 1024} KB)...", "")

        def _run():
            try:
                _download(url, dest, lambda done, total: self._progress_sig.emit(done, total))
                self._log_sig.emit("Download completo. Aplicando atualizacao...", C_SUCCESS)

                exe_name = Path(sys.executable).name
                bat = _write_updater(exe_dir, dest, exe_name)

                self._log_sig.emit(
                    f"Updater criado. O programa sera reiniciado em instantes...", C_SUCCESS
                )
                self._state_sig.emit("done")

                # Inicia o updater e fecha o app
                subprocess.Popen(
                    ["cmd", "/c", str(bat)],
                    cwd=str(exe_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
                    close_fds=True,
                )
                from PySide6.QtWidgets import QApplication
                QApplication.quit()

            except Exception as e:
                self._log_sig.emit(f"Erro ao baixar: {e}", C_ERROR)
                self._state_sig.emit("ready")

        threading.Thread(target=_run, daemon=True).start()

    def _open_github(self):
        repo = config.get("github_repo", "")
        if repo:
            import webbrowser
            webbrowser.open(f"https://github.com/{repo}/releases/latest")

    # ── Slots (main thread) ───────────────────────────────────────────────────

    def _show_release(self, release: dict):
        self._latest_release = release
        tag = release.get("tag_name", "")
        name = release.get("name", tag)
        body = release.get("body", "").strip()

        self._lbl_latest.setText(tag)

        if _is_newer(tag):
            self._lbl_latest.setStyleSheet(f"color: {C_SUCCESS}; font-weight: bold;")
            self._lbl_status.setText(f"Atualizacao disponivel!")
            self._lbl_status.setStyleSheet(f"color: {C_SUCCESS}; font-weight: bold;")
            self._log_sig.emit(f"Nova versao encontrada: {tag}", C_SUCCESS)
            self._state_sig.emit("ready")

            self._notes_title.setText(f"Novidades em {name}")
            self._notes_text.setPlainText(body or "Sem notas de release.")
            self._notes_frame.setVisible(True)
        else:
            self._lbl_latest.setStyleSheet(f"color: {C_TEXT_DIM};")
            self._lbl_status.setText("Voce ja tem a versao mais recente")
            self._lbl_status.setStyleSheet(f"color: {C_SUCCESS};")
            self._log_sig.emit("Nenhuma atualizacao disponivel.", C_SUCCESS)
            self._notes_frame.setVisible(False)
            self._state_sig.emit("idle")

        self._btn_github.setVisible(True)

    def _append_log(self, msg: str, color: str):
        if color:
            self._log.append(f'<span style="color:{color}">{msg}</span>')
        else:
            self._log.append(msg)

    def _update_progress(self, done: int, total: int):
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(done)
        else:
            self._progress.setRange(0, 0)

    def _apply_state(self, state: str):
        self._btn_check.setEnabled(state in ("idle", "ready"))
        self._btn_update.setVisible(state in ("ready", "downloading"))
        self._btn_update.setEnabled(state == "ready")
        self._progress.setVisible(state == "downloading")
        if state == "checking":
            self._progress.setVisible(True)
            self._progress.setRange(0, 0)
            self._lbl_status.setText("Verificando...")
            self._lbl_status.setStyleSheet(f"color: {C_TEXT_DIM};")
        if state == "idle":
            self._progress.setVisible(False)

    def on_activate(self):
        self._lbl_current.setText(f"v{VERSION}")
