import cv2
from PyQt5.QtWidgets import QLabel, QSizePolicy, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

class VideoPlayer(QWidget):
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(bool) # True = Playing, False = Paused

    def __init__(self):
        super().__init__()
        self.video_path = None
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.is_playing = False
        self.fps = 30
        self.total_frames = 0
        
        # Display label
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background-color: black;")
        self.label.setMinimumSize(640, 360)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def load_video(self, path):
        self.stop()
        if self.cap:
            self.cap.release()
            
        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        
        if not self.cap.isOpened():
            return False, "Could not open video file."
            
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = self.total_frames / self.fps
        
        self.durationChanged.emit(int(duration_sec * 1000)) # msecs
        
        # Show first frame
        self.next_frame()
        return True, ""

    def play(self):
        if self.cap and self.cap.isOpened():
            self.is_playing = True
            interval = int(1000 / self.fps)
            self.timer.start(interval)
            self.stateChanged.emit(True)

    def pause(self):
        self.is_playing = False
        self.timer.stop()
        self.stateChanged.emit(False)

    def stop(self):
        self.pause()
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.next_frame()

    def set_position(self, msecs):
        if self.cap and self.cap.isOpened():
            frame_idx = int((msecs / 1000) * self.fps)
            # Clamp
            frame_idx = max(0, min(frame_idx, self.total_frames - 1))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            self.next_frame()

    def next_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Convert BGR (OpenCV) to RGB (Qt)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # Scale to fit label keeping aspect ratio
                pixmap = QPixmap.fromImage(q_img)
                scaled_pixmap = pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.label.setPixmap(scaled_pixmap)
                
                # Emit position
                current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                current_msec = int((current_frame / self.fps) * 1000)
                
                # Only emit if playing to avoid loops during seek
                if self.is_playing:
                    self.positionChanged.emit(current_msec)
            else:
                # Loop or stop at end
                self.pause()

    def state(self):
        return self.is_playing
