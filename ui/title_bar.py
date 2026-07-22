from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QStyle
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QMouseEvent, QIcon

class CustomTitleBar(QWidget):
    """A modern, custom title bar for the main window."""
    
    def __init__(self, parent, title="Video AI Voiceover Tool"):
        super().__init__(parent)
        self.parent = parent
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 0, 0)
        self.setFixedHeight(40)
        
        # Style
        self.setObjectName("CustomTitleBar")
        # Note: Background color will be set via stylesheet in the main window
        
        # Title Label
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #E0E0E0; font-weight: 600; font-size: 13px; padding-left: 5px;")
        self.layout.addWidget(self.title_label)
        
        self.layout.addStretch()
        
        # Window Buttons
        self.btn_minimize = QPushButton()
        self.btn_minimize.setFixedSize(45, 40)
        self.btn_minimize.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMinButton))
        self.btn_minimize.clicked.connect(self.parent.showMinimized)
        
        self.btn_maximize = QPushButton()
        self.btn_maximize.setFixedSize(45, 40)
        self.btn_maximize.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        self.btn_maximize.clicked.connect(self.toggle_maximize)
        
        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(45, 40)
        self.btn_close.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        self.btn_close.clicked.connect(self.parent.close)
        
        # Modern button styling
        btn_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 0px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #333334;
            }
        """
        self.btn_minimize.setStyleSheet(btn_style)
        self.btn_maximize.setStyleSheet(btn_style)
        
        # Close button has a red hover effect
        close_btn_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 0px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #E81123;
            }
        """
        self.btn_close.setStyleSheet(close_btn_style)
        
        self.layout.addWidget(self.btn_minimize)
        self.layout.addWidget(self.btn_maximize)
        self.layout.addWidget(self.btn_close)
        self.layout.setContentsMargins(10, 0, 0, 0) # No padding on the right to flush buttons
        
        # Dragging support
        self.start_pos = None

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.btn_maximize.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        else:
            self.parent.showMaximized()
            self.btn_maximize.setIcon(self.style().standardIcon(QStyle.SP_TitleBarNormalButton))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.globalPos()
            
    def mouseMoveEvent(self, event):
        if self.start_pos:
            delta = QPoint(event.globalPos() - self.start_pos)
            self.parent.move(self.parent.x() + delta.x(), self.parent.y() + delta.y())
            self.start_pos = event.globalPos()
            
    def mouseReleaseEvent(self, event):
        self.start_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_maximize()
