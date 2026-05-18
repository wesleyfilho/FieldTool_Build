"""Dark theme stylesheet for FieldTool."""

# Color palette
C_BG        = "#0d1117"
C_SIDEBAR   = "#161b22"
C_CARD      = "#21262d"
C_CARD2     = "#30363d"
C_BORDER    = "#30363d"
C_ACCENT    = "#1f6feb"
C_ACCENT2   = "#388bfd"
C_TEXT      = "#e6edf3"
C_TEXT_DIM  = "#8b949e"
C_SUCCESS   = "#3fb950"
C_WARNING   = "#d29922"
C_ERROR     = "#f85149"
C_MKTIK     = "#cc6600"   # MikroTik orange
C_UBNT      = "#0066cc"   # Ubiquiti blue
C_LOCAL     = "#a371f7"   # Local PC purple

DARK_THEME = f"""
QMainWindow, QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}}

/* ── Sidebar ── */
#sidebar {{
    background-color: {C_SIDEBAR};
    border-right: 1px solid {C_BORDER};
    min-width: 200px;
    max-width: 200px;
}}

#logo_label {{
    color: {C_ACCENT2};
    font-size: 15px;
    font-weight: bold;
    padding: 16px 12px 8px 12px;
    border-bottom: 1px solid {C_BORDER};
}}

#version_label {{
    color: {C_TEXT_DIM};
    font-size: 10px;
    padding: 0 12px 12px 12px;
}}

QPushButton#nav_btn {{
    background-color: transparent;
    color: {C_TEXT_DIM};
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    text-align: left;
    font-size: 13px;
    margin: 1px 6px;
}}
QPushButton#nav_btn:hover {{
    background-color: {C_CARD2};
    color: {C_TEXT};
}}
QPushButton#nav_btn[active="true"] {{
    background-color: {C_ACCENT};
    color: white;
    font-weight: 600;
}}

/* ── Cards ── */
QFrame#card {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 4px;
}}

QLabel#stat_value {{
    color: {C_ACCENT2};
    font-size: 28px;
    font-weight: bold;
}}
QLabel#stat_label {{
    color: {C_TEXT_DIM};
    font-size: 11px;
}}
QLabel#section_title {{
    color: {C_TEXT};
    font-size: 15px;
    font-weight: bold;
    padding: 4px 0;
}}
QLabel#page_title {{
    color: {C_TEXT};
    font-size: 18px;
    font-weight: bold;
}}

/* ── Tables ── */
QTableWidget {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    gridline-color: {C_BORDER};
    selection-background-color: {C_ACCENT};
    selection-color: white;
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 10px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: {C_ACCENT};
    color: white;
}}
QHeaderView::section {{
    background-color: {C_CARD2};
    color: {C_TEXT_DIM};
    border: none;
    border-right: 1px solid {C_BORDER};
    border-bottom: 1px solid {C_BORDER};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {C_CARD2};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {C_ACCENT};
    border-color: {C_ACCENT};
    color: white;
}}
QPushButton:pressed {{
    background-color: #1158c7;
}}
QPushButton:disabled {{
    color: {C_TEXT_DIM};
    background-color: {C_CARD};
    border-color: {C_BORDER};
}}
QPushButton#btn_primary {{
    background-color: {C_ACCENT};
    color: white;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_primary:hover {{
    background-color: {C_ACCENT2};
}}
QPushButton#btn_success {{
    background-color: {C_SUCCESS};
    color: white;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_danger {{
    background-color: {C_ERROR};
    color: white;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_danger:hover {{
    background-color: #ff6b6b;
}}

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {C_CARD};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: {C_ACCENT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {C_ACCENT};
}}
QComboBox {{
    background-color: {C_CARD};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    min-width: 120px;
}}
QComboBox:focus {{
    border-color: {C_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {C_CARD};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    selection-background-color: {C_ACCENT};
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {C_CARD};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 6px 8px;
}}
QCheckBox {{
    color: {C_TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid {C_BORDER};
    background: {C_CARD};
}}
QCheckBox::indicator:checked {{
    background-color: {C_ACCENT};
    border-color: {C_ACCENT};
}}

/* ── ScrollBars ── */
QScrollBar:vertical {{
    background: {C_BG};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C_CARD2};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C_TEXT_DIM};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {C_BG};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {C_CARD2};
    border-radius: 4px;
    min-width: 30px;
}}

/* ── Status Bar ── */
QStatusBar {{
    background-color: {C_SIDEBAR};
    color: {C_TEXT_DIM};
    border-top: 1px solid {C_BORDER};
    padding: 2px 8px;
    font-size: 12px;
}}
QStatusBar::item {{
    border: none;
}}

/* ── Progress Bar ── */
QProgressBar {{
    background-color: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {C_ACCENT};
    border-radius: 4px;
}}

/* ── GroupBox ── */
QGroupBox {{
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
    color: {C_TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
}}

/* ── Tab Widget ── */
QTabWidget::pane {{
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    background: {C_CARD};
}}
QTabBar::tab {{
    background: {C_CARD2};
    color: {C_TEXT_DIM};
    border: 1px solid {C_BORDER};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    padding: 8px 16px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {C_CARD};
    color: {C_TEXT};
    border-bottom-color: {C_CARD};
}}
QTabBar::tab:hover {{
    background: {C_CARD};
    color: {C_TEXT};
}}

/* ── Splitter ── */
QSplitter::handle {{
    background: {C_BORDER};
}}

/* ── Tooltip ── */
QToolTip {{
    background-color: {C_CARD2};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ── Menu ── */
QMenu {{
    background-color: {C_CARD};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 16px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {C_ACCENT};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {C_BORDER};
    margin: 4px 8px;
}}

/* ── Message Box ── */
QMessageBox {{
    background-color: {C_CARD};
}}

/* ── Label colors ── */
QLabel#status_online  {{ color: {C_SUCCESS}; font-weight: bold; }}
QLabel#status_offline {{ color: {C_ERROR}; font-weight: bold; }}
QLabel#tag_mikrotik   {{ color: {C_MKTIK}; font-weight: bold; }}
QLabel#tag_ubnt       {{ color: {C_UBNT}; font-weight: bold; }}
"""

STATUS_COLORS = {
    "online":  C_SUCCESS,
    "offline": C_ERROR,
}

OS_COLORS = {
    "mikrotik": C_MKTIK,
    "ubiquiti": C_UBNT,
    "local":    C_LOCAL,
    "unknown":  C_TEXT_DIM,
}

LOG_COLORS = {
    "INFO":    C_TEXT,
    "SUCCESS": C_SUCCESS,
    "WARNING": C_WARNING,
    "ERROR":   C_ERROR,
}
