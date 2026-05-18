"""FieldTool — entry point."""

import sys
import os
import logging
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPalette, QFont

from app.core.config import config
from app.database.db import _get_conn


def _setup_logging():
    log_path = Path(config.get("log_path"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_path), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _load_builtin_templates():
    try:
        from app.templates.manager import load_builtin_templates
        load_builtin_templates()
    except Exception as e:
        logging.warning(f"Failed to load built-in templates: {e}")


def _log_startup():
    from app.database import db as _db
    _db.add_log("INFO", "SYSTEM", "FieldTool iniciado")


def main():
    _setup_logging()

    # Init database before starting UI
    try:
        _get_conn()
    except Exception as e:
        logging.error(f"Database init failed: {e}")

    _load_builtin_templates()

    app = QApplication(sys.argv)
    app.setApplicationName("FieldTool")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("FieldTool")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Dark palette baseline (stylesheet does the heavy lifting)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor("#0d1117"))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.Base,            QColor("#21262d"))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#161b22"))
    palette.setColor(QPalette.ColorRole.Text,            QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.Button,          QColor("#21262d"))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#e6edf3"))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor("#1f6feb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    # Splash screen
    splash = QSplashScreen()
    splash.setFixedSize(480, 240)
    splash.setStyleSheet("""
        background-color: #0d1117;
        border: 1px solid #30363d;
        border-radius: 12px;
    """)
    splash_label = QLabel(splash)
    splash_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    splash_label.setGeometry(0, 0, 480, 240)
    splash_label.setText(
        '<div style="color:#388bfd;font-size:28px;font-weight:bold;font-family:Segoe UI;">'
        'FieldTool</div>'
        '<div style="color:#8b949e;font-size:13px;margin-top:8px;">Carregando...</div>'
        '<div style="color:#3fb950;font-size:11px;margin-top:20px;">100% Offline</div>'
    )
    splash.show()
    app.processEvents()

    from app.ui.main_window import MainWindow

    window = MainWindow()

    _log_startup()

    def _finish_splash():
        splash.finish(window)
        window.show()
        window.activateWindow()

    QTimer.singleShot(1200, _finish_splash)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
