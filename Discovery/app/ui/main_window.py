"""Main application window with sidebar navigation."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QStatusBar,
    QProgressBar, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon

from app.ui.styles import DARK_THEME
from app.ui.dashboard import DashboardPage
from app.ui.discovery import DiscoveryPage
from app.ui.ip_locator import IPLocatorPage
from app.ui.auto_config import AutoConfigPage
from app.ui.templates_view import TemplatesPage
from app.ui.logs_view import LogsPage
from app.ui.settings_view import SettingsPage
from app.ui.nic_config import NICConfigPage
from app.ui.backups_view import BackupsPage
from app.ui.updates_view import UpdatesPage

NAV_ITEMS = [
    ("dashboard",   "  Dashboard",       "Dashboard"),
    ("discovery",   "  Discovery",       "Descoberta de Rede"),
    ("ip_locator",  "  IP Locator",      "Localizador de IP"),
    ("auto_config", "  Auto Config",     "Configuracao Automatica"),
    ("nic_config",  "  NIC Config",      "Configurar Placa de Rede"),
    ("backups",     "  Backups",         "Backups de Configuracao"),
    ("templates",   "  Templates",       "Gerenciar Templates"),
    ("logs",        "  Logs",            "Historico e Logs"),
    ("updates",     "  Atualizacoes",    "Atualizacoes do Sistema"),
    ("settings",    "  Configuracoes",   "Configuracoes do Sistema"),
]


class SidebarButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("nav_btn")
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(40)
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FieldTool")
        self.setMinimumSize(1200, 700)
        self.resize(1280, 780)
        self.setStyleSheet(DARK_THEME)

        self._pages: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, SidebarButton] = {}
        self._current_page = ""

        self._build_ui()
        self._navigate("dashboard")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        logo = QLabel("  FieldTool")
        logo.setObjectName("logo_label")
        logo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))

        version = QLabel("  v1.0")
        version.setObjectName("version_label")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(version)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        sidebar_layout.addWidget(divider)
        sidebar_layout.addSpacing(8)

        # Nav buttons
        for key, label, _ in NAV_ITEMS:
            btn = SidebarButton(label)
            btn.clicked.connect(lambda checked=False, k=key: self._navigate(k))
            self._nav_buttons[key] = btn
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Bottom info
        info = QLabel("  100% Offline")
        info.setObjectName("version_label")
        sidebar_layout.addWidget(info)
        sidebar_layout.addSpacing(8)

        root_layout.addWidget(sidebar)

        # ── Content area ──
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stack of pages
        self._stack = QStackedWidget()

        page_classes = {
            "dashboard":   DashboardPage,
            "discovery":   DiscoveryPage,
            "ip_locator":  IPLocatorPage,
            "auto_config": AutoConfigPage,
            "nic_config":  NICConfigPage,
            "backups":     BackupsPage,
            "updates":     UpdatesPage,
            "templates":   TemplatesPage,
            "logs":        LogsPage,
            "settings":    SettingsPage,
        }

        for key, cls in page_classes.items():
            try:
                page = cls()
            except Exception as e:
                page = QLabel(f"Erro ao carregar pagina {key}:\n{e}")
                page.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._pages[key] = page
            self._stack.addWidget(page)

        # Connect discovery page scan signal to dashboard refresh
        if "discovery" in self._pages and "dashboard" in self._pages:
            disc: DiscoveryPage = self._pages["discovery"]
            dash: DashboardPage = self._pages["dashboard"]
            if hasattr(disc, "scan_finished"):
                disc.scan_finished.connect(dash.refresh)

        content_layout.addWidget(self._stack)
        root_layout.addWidget(content_wrapper, 1)

        # ── Status bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("Pronto")
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(200)
        self._progress.setMaximumHeight(8)
        self._progress.setVisible(False)

        self._status_bar.addWidget(self._status_label, 1)
        self._status_bar.addPermanentWidget(self._progress)

        # Wire up status from discovery page
        if "discovery" in self._pages:
            disc: DiscoveryPage = self._pages["discovery"]
            if hasattr(disc, "status_changed"):
                disc.status_changed.connect(self._on_status)
            if hasattr(disc, "scan_progress"):
                disc.scan_progress.connect(self._on_progress)

    def _navigate(self, key: str):
        if key not in self._pages:
            return
        if self._current_page and self._current_page in self._nav_buttons:
            self._nav_buttons[self._current_page].set_active(False)

        self._current_page = key
        self._nav_buttons[key].set_active(True)
        self._stack.setCurrentWidget(self._pages[key])

        # Update window title with page name
        page_title = next((t for k, _, t in NAV_ITEMS if k == key), "")
        self.setWindowTitle(f"FieldTool — {page_title}")

        # Notify page of activation
        page = self._pages[key]
        if hasattr(page, "on_activate"):
            page.on_activate()

    def _on_status(self, msg: str):
        self._status_label.setText(msg)

    def _on_progress(self, msg: str, current: int, total: int):
        self._status_label.setText(msg)
        if total > 0:
            self._progress.setVisible(True)
            self._progress.setRange(0, total)
            self._progress.setValue(current)
        else:
            self._progress.setVisible(True)
            self._progress.setRange(0, 0)  # indeterminate

    def show_status(self, msg: str, timeout: int = 4000):
        self._status_label.setText(msg)
        if timeout:
            QTimer.singleShot(timeout, lambda: self._status_label.setText("Pronto"))

    def hide_progress(self):
        self._progress.setVisible(False)
