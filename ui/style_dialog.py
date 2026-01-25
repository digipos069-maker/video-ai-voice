from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFontComboBox, QSpinBox, QPushButton, QCheckBox, 
                             QColorDialog, QDialogButtonBox, QGroupBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont

class SubtitleStyleDialog(QDialog):
    styleChanged = pyqtSignal(dict) # Signal for live preview

    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Subtitle Style")
        self.resize(400, 300)
        self.settings = current_settings.copy()
        self.original_settings = current_settings.copy() # Backup for cancel
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Font Group
        font_group = QGroupBox("Font Settings")
        font_layout = QVBoxLayout()
        
        # Family
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Family:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.settings['font_family']))
        self.font_combo.currentFontChanged.connect(self.emit_change) # Live update
        font_row.addWidget(self.font_combo)
        font_layout.addLayout(font_row)
        
        # Size
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 100)
        self.size_spin.setValue(self.settings['font_size'])
        self.size_spin.valueChanged.connect(self.emit_change) # Live update
        size_row.addWidget(self.size_spin)
        font_layout.addLayout(size_row)
        
        # Style
        style_row = QHBoxLayout()
        self.chk_bold = QCheckBox("Bold")
        self.chk_bold.setChecked(self.settings['is_bold'])
        self.chk_bold.toggled.connect(self.emit_change) # Live update
        
        self.chk_italic = QCheckBox("Italic")
        self.chk_italic.setChecked(self.settings['is_italic'])
        self.chk_italic.toggled.connect(self.emit_change) # Live update
        
        style_row.addWidget(self.chk_bold)
        style_row.addWidget(self.chk_italic)
        font_layout.addLayout(style_row)
        
        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        # Color Group
        color_group = QGroupBox("Colors")
        color_layout = QVBoxLayout()
        
        # Text Color
        self.btn_color = QPushButton("Text Color")
        self.btn_color.setStyleSheet(f"background-color: {self.settings['color']}; color: black;")
        self.btn_color.clicked.connect(self.pick_text_color)
        color_layout.addWidget(self.btn_color)
        
        # Background Color (Transparent Toggle)
        bg_row = QHBoxLayout()
        self.chk_bg_transparent = QCheckBox("Transparent Background")
        is_transparent = self.settings['bg_color'] == 'transparent'
        self.chk_bg_transparent.setChecked(is_transparent)
        self.chk_bg_transparent.toggled.connect(self.emit_change) # Live update
        
        self.btn_bg_color = QPushButton("Background Color")
        self.btn_bg_color.setEnabled(not is_transparent)
        self.btn_bg_color.clicked.connect(self.pick_bg_color)
        
        self.chk_bg_transparent.toggled.connect(self.btn_bg_color.setDisabled)
        
        bg_row.addWidget(self.chk_bg_transparent)
        bg_row.addWidget(self.btn_bg_color)
        color_layout.addLayout(bg_row)
        
        # Padding
        pad_row = QHBoxLayout()
        pad_row.addWidget(QLabel("Background Padding:"))
        self.pad_spin = QSpinBox()
        self.pad_spin.setRange(0, 50)
        self.pad_spin.setValue(self.settings.get('padding', 0)) # Default 0
        self.pad_spin.valueChanged.connect(self.emit_change)
        pad_row.addWidget(self.pad_spin)
        color_layout.addLayout(pad_row)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)

        # Dialog Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def emit_change(self):
        """Emits current settings for live preview."""
        self.styleChanged.emit(self.get_settings())

    def pick_text_color(self):
        color = QColorDialog.getColor(QColor(self.settings['color']), self, "Select Text Color")
        if color.isValid():
            self.settings['color'] = color.name()
            self.btn_color.setStyleSheet(f"background-color: {color.name()}; color: black;")
            self.emit_change() # Live update

    def pick_bg_color(self):
        current = self.settings['bg_color']
        if current == 'transparent':
            current = '#000000'
        color = QColorDialog.getColor(QColor(current), self, "Select Background Color")
        if color.isValid():
            self.settings['bg_color'] = color.name()
            self.emit_change() # Live update

    def get_settings(self):
        # Update settings from widgets before returning
        self.settings['font_family'] = self.font_combo.currentFont().family()
        self.settings['font_size'] = self.size_spin.value()
        self.settings['is_bold'] = self.chk_bold.isChecked()
        self.settings['is_italic'] = self.chk_italic.isChecked()
        self.settings['padding'] = self.pad_spin.value()
        
        if self.chk_bg_transparent.isChecked():
            self.settings['bg_color'] = 'transparent'
            
        return self.settings
