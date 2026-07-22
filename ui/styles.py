PRIMARY_COLOR = "#032EA1"
TITLE_BAR_COLOR = "#1E1E24"  # Modern Deep Charcoal
TEXT_COLOR = "#333333"
BACKGROUND_COLOR = "#F8F9FA" # Brighter, cleaner light background
WHITE = "#FFFFFF"

STYLESHEET = f"""
QMainWindow {{
    background-color: {BACKGROUND_COLOR};
}}

#CustomTitleBar {{
    background-color: {TITLE_BAR_COLOR};
    border-bottom: 1px solid #121212;
}}

QWidget {{
    font-family: 'Segoe UI', 'Leelawadee UI', sans-serif;
    font-size: 14px;
    color: {TEXT_COLOR};
}}

QTabWidget::pane {{
    border: 1px solid #CCCCCC;
    background: {WHITE};
}}

QTabBar::tab {{
    background: #E0E0E0;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    qproperty-cursor: "PointingHandCursor";
}}

QTabBar::tab:selected {{
    background: {WHITE};
    border-bottom: 2px solid {PRIMARY_COLOR};
    font-weight: bold;
    color: {PRIMARY_COLOR};
}}

QPushButton {{
    background-color: {PRIMARY_COLOR};
    color: {WHITE};
    border: none;
    padding: 10px 20px;
    border-radius: 4px;
    font-weight: bold;
    qproperty-cursor: "PointingHandCursor";
}}

QPushButton:hover {{
    background-color: #02237A;
    qproperty-cursor: "PointingHandCursor";
}}

QComboBox, QCheckBox, QHeaderView, QTabBar {{
    qproperty-cursor: "PointingHandCursor";
}}

QSlider {{
    qproperty-cursor: "OpenHandCursor";
}}

QSlider::handle:horizontal {{
    qproperty-cursor: "OpenHandCursor";
}}

QPushButton:pressed {{
    background-color: #011855;
}}

QTableWidget {{
    background-color: {WHITE};
    gridline-color: #EEEEEE;
    border: 1px solid #CCCCCC;
}}

QHeaderView::section {{
    background-color: {PRIMARY_COLOR};
    color: {WHITE};
    padding: 5px;
    border: none;
}}

QLabel {{
    font-weight: normal;
}}

QGroupBox {{
    font-weight: bold;
    border: 1px solid #CCCCCC;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 15px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: {PRIMARY_COLOR};
}}
"""
