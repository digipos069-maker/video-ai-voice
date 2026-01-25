PRIMARY_COLOR = "#032EA1"
TEXT_COLOR = "#333333"
BACKGROUND_COLOR = "#F5F5F5"
WHITE = "#FFFFFF"

STYLESHEET = f"""
QMainWindow {{
    background-color: {BACKGROUND_COLOR};
}}

QWidget {{
    font-family: 'Segoe UI', sans-serif;
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
}}

QPushButton:hover {{
    background-color: #02237A;
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
