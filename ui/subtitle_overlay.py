from PyQt5.QtWidgets import QLabel, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QFont, QColor, QPalette

class SubtitleOverlay(QLabel):
    doubleClicked = pyqtSignal() # Signal to open editor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        
        # Default Style
        self.style_settings = {
            'font_family': 'Arial',
            'font_size': 24,
            'color': '#FFFFFF',
            'outline_color': '#000000',
            'is_bold': True,
            'is_italic': False,
            'bg_color': 'transparent' # Or rgba(0,0,0,150)
        }
        
        # Internal state for dragging
        self.dragging = False
        self.offset = QPoint()
        
        self.update_style()
        self.setText("")
        self.hide()

    def update_style(self, settings=None):
        if settings:
            self.style_settings.update(settings)
            
        s = self.style_settings
        
        # Apply Font
        font = QFont(s['font_family'], s['font_size'])
        font.setBold(s['is_bold'])
        font.setItalic(s['is_italic'])
        self.setFont(font)
        
        # Apply Colors via Stylesheet (easiest for QLabel)
        # Note: Outline is faked with text-shadow or we use QGraphicsEffect. 
        # Getting a true stroke in QLabel is hard, so we use a shadow effect for readability.
        self.setStyleSheet(f"""
            QLabel {{
                color: {s['color']};
                background-color: {s['bg_color']};
                padding: 4px;
                border-radius: 4px;
            }}
        """)
        
        # Add Shadow/Outline effect
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(2)
        effect.setColor(QColor(s['outline_color']))
        effect.setOffset(1, 1)
        self.setGraphicsEffect(effect)
        
        self.adjustSize()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.dragging:
            # Move widget relative to parent
            new_pos = self.mapToParent(event.pos() - self.offset)
            
            # Constrain to parent bounds (optional but good)
            parent_rect = self.parent().rect()
            
            # Simple clamping
            x = max(0, min(new_pos.x(), parent_rect.width() - self.width()))
            y = max(0, min(new_pos.y(), parent_rect.height() - self.height()))
            
            self.move(x, y)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
