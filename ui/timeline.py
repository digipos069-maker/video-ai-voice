from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen

class TimelineLane(QWidget):

    seekRequested = pyqtSignal(int) # Emits msecs



    def __init__(self, track_type="video", color="#333333"):

        super().__init__()

        self.track_type = track_type

        self.base_color = QColor(color)

        self.segments = [] # For AI track

        self.duration_ms = 1 # Avoid div by zero

        self.setFixedHeight(40) # Height of the track

        self.current_time_ms = 0

        self.setCursor(Qt.PointingHandCursor) # Indicate clickable



    def set_duration(self, duration_ms):


        self.duration_ms = max(1, duration_ms)
        self.update()

    def set_segments(self, segments):
        """segments: list of {'start': float (sec), ...}"""
        self.segments = segments
        self.update()

    def set_current_time(self, msecs):
        self.current_time_ms = msecs
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Draw Background
        painter.fillRect(0, 0, w, h, QColor("#E0E0E0"))
        
        # Calculate pixels per ms
        px_per_ms = w / self.duration_ms
        
        # Draw Track Content
        if self.track_type in ["video", "audio"]:
            # Draw continuous bar
            painter.fillRect(0, 2, w, h-4, self.base_color)
            
            # Simple "Pattern" to distinguish (optional)
            if self.track_type == "audio":
                pen = QPen(QColor(255,255,255, 50))
                pen.setWidth(1)
                painter.setPen(pen)
                for i in range(0, w, 10):
                    painter.drawLine(i, 2, i, h-4)

        elif self.track_type == "ai":
            # Draw segments
            brush = QBrush(self.base_color)
            for seg in self.segments:
                start_ms = seg['start'] * 1000
                # Approximate duration if not provided, assume 2s or calc from end
                end_ms = seg.get('end', seg['start'] + 2.0) * 1000 
                
                x = int(start_ms * px_per_ms)
                width = int((end_ms - start_ms) * px_per_ms)
                width = max(2, width) # Min width visibility
                
                painter.fillRect(x, 2, width, h-4, brush)
                
                # Draw text hint (optional)
                painter.setPen(Qt.white)
                # painter.drawText(x+2, h//2 + 5, seg.get('text', '')[:5])

        # Draw Playhead
        playhead_x = int(self.current_time_ms * px_per_ms)
        painter.setPen(QPen(QColor("red"), 2))
        painter.drawLine(playhead_x, 0, playhead_x, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._calculate_seek(event.x())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._calculate_seek(event.x())

    def _calculate_seek(self, x):
        width = self.width()
        if width > 0:
            ratio = max(0, min(x, width)) / width
            seek_time = int(ratio * self.duration_ms)
            self.seekRequested.emit(seek_time)
