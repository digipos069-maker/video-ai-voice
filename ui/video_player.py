import cv2
import os
import subprocess
import imageio_ffmpeg
from moviepy import AudioFileClip
from PyQt5.QtWidgets import QLabel, QSizePolicy, QWidget, QVBoxLayout, QMessageBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QUrl, QSize
from PyQt5.QtGui import QImage, QPixmap, QIcon
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

from ui.subtitle_overlay import SubtitleOverlay
from ui.style_dialog import SubtitleStyleDialog

class VideoPlayer(QWidget):
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(bool) # True = Playing, False = Paused
    importRequested = pyqtSignal() # Signal to request video import
    thumbnailReady = pyqtSignal(QPixmap) # Signal when thumbnail is generated

    def __init__(self):
        super().__init__()
        self.video_path = None
        self.cap = None
        self.video_visible = True
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)
        self.is_playing = False
        self.fps = 30
        self.total_frames = 0
        self.current_msec = 0
        
        # Audio Player 1: Original Video Sound
        self.orig_player = QMediaPlayer(None, QMediaPlayer.LowLatency)
        self.orig_player.error.connect(self._handle_audio_error)
        
        # Audio Player 2: AI Voiceover
        self.ai_player = QMediaPlayer(None, QMediaPlayer.LowLatency)
        self.ai_player.setVolume(100)
        self.ai_segments = [] # List of {'start': float, 'path': str}
        self.next_ai_index = 0
        self.current_ai_end = None
        
        # Subtitle Data
        self.subtitles = [] # List of {'start': float, 'end': float, 'text': str}
        self.current_subtitle_index = -1

        # Display label
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background-color: #333333; color: #AAAAAA; font-size: 16px;")
        self.label.setMinimumSize(640, 360)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Subtitle Overlay (Child of the video label)
        self.sub_overlay = SubtitleOverlay(self.label)
        self.sub_overlay.doubleClicked.connect(self.open_style_editor)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        self.show_placeholder()

    def show_placeholder(self):
        """Displays the placeholder icon and text."""
        # Create a placeholder pixmap/text
        self.label.clear()
        self.label.setText("No Video Selected\n\nClick here or 'Import Video' to start")
        
        # Add pointing hand cursor to indicate it's clickable
        self.label.setCursor(Qt.PointingHandCursor)
        
        # Ensure overlay is hidden
        self.sub_overlay.hide()

    def set_subtitles(self, subtitles):
        """
        subtitles: List of dicts {'start': float, 'end': float, 'text': str}
        """
        self.subtitles = sorted(subtitles, key=lambda x: x['start'])
        self.sub_overlay.show() if subtitles else self.sub_overlay.hide()
        # Default Position (Bottom Center)
        self.sub_overlay.move(50, self.label.height() - 100)

    def mousePressEvent(self, event):
        if not self.video_path and event.button() == Qt.LeftButton:
            self.importRequested.emit()
        super().mousePressEvent(event)

    def open_style_editor(self):
        self.pause() # Pause video while editing
        original_settings = self.sub_overlay.style_settings.copy()
        
        dialog = SubtitleStyleDialog(original_settings, self)
        
        # Connect Live Preview
        dialog.styleChanged.connect(self.sub_overlay.update_style)
        
        if dialog.exec_():
            # Accepted: Keep changes (already applied via signals or get final state)
            new_settings = dialog.get_settings()
            self.sub_overlay.update_style(new_settings)
        else:
            # Rejected: Revert to original
            self.sub_overlay.update_style(original_settings)

    def _handle_audio_error(self):
        err = self.orig_player.errorString()
        print(f"Original Audio Error: {err}")

    def set_video_visible(self, visible):
        self.video_visible = visible
        if not visible:
            self.label.clear()
            self.label.setStyleSheet("background-color: black;")
        else:
            self.next_frame() # Refresh frame immediately

    def load_video(self, path):
        self.stop()
        if self.cap:
            self.cap.release()
            
        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        
        if not self.cap.isOpened():
            self.show_placeholder()
            return False, "Could not open video file."
            
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_sec = self.total_frames / self.fps
        
        # --- Extract Thumbnail ---
        ret, frame = self.cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            thumb_pixmap = QPixmap.fromImage(q_img).scaled(64, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumbnailReady.emit(thumb_pixmap)
            
            # Reset to start
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        # -------------------------
        
        # --- FIX: Extract audio to temporary WAV for guaranteed playback ---
        temp_audio = os.path.join(os.getcwd(), "temp_preview_audio.wav")
        try:
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
                
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i", path,
                "-vn",
                "-acodec", "pcm_s16le", # WAV format (widely supported)
                "-ar", "44100",
                "-ac", "1", # Mono is more compatible for some drivers
                temp_audio
            ]
            # Run fast extraction
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0, check=True)
            
            # Load the extracted WAV
            url = QUrl.fromLocalFile(temp_audio)
            self.orig_player.setMedia(QMediaContent(url))
            
        except Exception as e:
            print(f"Audio extraction failed: {e}")
            # Fallback to original file (might fail with 0x80040266 but worth a try)
            url = QUrl.fromLocalFile(path)
            self.orig_player.setMedia(QMediaContent(url))
        # -------------------------------------------------------------------
        
        self.durationChanged.emit(int(duration_sec * 1000)) # msecs
        self.current_msec = 0
        
        # Reset cursor from placeholder pointing hand to default
        self.label.setCursor(Qt.ArrowCursor)
        
        # Show first frame
        self.next_frame()
        return True, ""

    def load_ai_segments(self, segments):
        """
        segments: List of dicts {'start': float, 'path': str} (start is in seconds)
        """
        # Sort by start time just in case
        sorted_segments = sorted(segments, key=lambda x: x['start'])
        self.ai_segments = []
        for i, seg in enumerate(sorted_segments):
            seg_copy = dict(seg)
            start = seg_copy.get('start')
            end = seg_copy.get('end')
            if start is not None and end is not None and end <= start:
                end = start + 0.05
            seg_copy['_effective_end'] = end
            seg_copy['preview_path'] = self._convert_ai_audio_for_preview(
                seg['path'],
                i,
                start,
                end
            )
            self.ai_segments.append(seg_copy)
        self.next_ai_index = 0
        self.current_ai_end = None

    def _convert_ai_audio_for_preview(self, path, index, start, end):
        """Convert AI audio to WAV to avoid DirectShow decode errors."""
        if not path or not os.path.exists(path):
            return path
        temp_dir = os.path.join(os.getcwd(), "temp_preview_ai")
        os.makedirs(temp_dir, exist_ok=True)
        preview_path = os.path.join(temp_dir, f"ai_{index}.wav")
        if os.path.exists(preview_path):
            return preview_path
        try:
            target_duration = None
            if start is not None and end is not None:
                target_duration = max(0.05, float(end) - float(start))

            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            afilter = None
            if target_duration is not None:
                afilter = f"atrim=0:{target_duration:.3f}"
            cmd = [
                ffmpeg_exe,
                "-y",
                "-i", path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "1",
                "-filter:a", afilter if afilter else "anull",
                preview_path
            ]
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0, check=True)
            return preview_path
        except Exception:
            return path

    def play(self):
        if self.cap and self.cap.isOpened():
            self.is_playing = True
            interval = int(1000 / self.fps)
            self.timer.start(interval)
            
            # Play original audio
            self.orig_player.play()
            
            # AI player is triggered in next_frame logic, but if we are resuming inside a segment, handling is complex.
            # For simplicity, we just resume checking triggers.
            if self.ai_player.state() == QMediaPlayer.PausedState:
                self.ai_player.play()
                
            self.stateChanged.emit(True)

    def pause(self):
        self.is_playing = False
        self.timer.stop()
        self.orig_player.pause()
        self.ai_player.pause()
        self.stateChanged.emit(False)

    def stop(self):
        self.pause()
        self.orig_player.stop()
        self.ai_player.stop()
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.next_frame()
        self.current_msec = 0
        self.next_ai_index = 0
        self.current_ai_end = None

    def release_audio(self):
        """Releases file locks on audio files."""
        self.stop()
        self.orig_player.setMedia(QMediaContent())
        self.ai_player.setMedia(QMediaContent())
        self.ai_segments = []
        preview_dir = os.path.join(os.getcwd(), "temp_preview_ai")
        if os.path.isdir(preview_dir):
            for f in os.listdir(preview_dir):
                try:
                    os.remove(os.path.join(preview_dir, f))
                except Exception:
                    pass
            try:
                os.rmdir(preview_dir)
            except Exception:
                pass

    def set_position(self, msecs):
        if self.cap and self.cap.isOpened():
            self.current_msec = msecs
            
            # Sync Video
            frame_idx = int((msecs / 1000) * self.fps)
            frame_idx = max(0, min(frame_idx, self.total_frames - 1))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            self.next_frame()
            
            # Sync Original Audio
            self.orig_player.setPosition(msecs)
            
            # Reset AI Index
            # Find the next segment that starts AFTER current time
            self.next_ai_index = len(self.ai_segments)
            current_sec = msecs / 1000.0
            for i, seg in enumerate(self.ai_segments):
                if seg['start'] > current_sec:
                    self.next_ai_index = i
                    break
            
            # Stop AI player if seeking (simple approach)
            self.ai_player.stop()
            self.current_ai_end = None

    def set_orig_volume(self, volume):
        self.orig_player.setVolume(volume)

    def set_ai_volume(self, volume):
        self.ai_player.setVolume(volume)

    def next_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # Video Rendering
                if self.video_visible:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame.shape
                    bytes_per_line = ch * w
                    q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    
                    pixmap = QPixmap.fromImage(q_img)
                    scaled_pixmap = pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.label.setPixmap(scaled_pixmap)
                
                # Update Time State
                current_frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
                self.current_msec = int((current_frame / self.fps) * 1000)
                current_sec = self.current_msec / 1000.0
                
                # Update Subtitle Text
                found_sub = False
                
                # Simple optimization: check surrounding subtitles first if index known, but simple loop is fast enough for <1000 subs
                for sub in self.subtitles:
                    # Precise sync: start <= time < end
                    if sub['start'] <= current_sec < sub['end']:
                        if self.sub_overlay.text() != sub['text']:
                            self.sub_overlay.setText(sub['text'])
                            self.sub_overlay.adjustSize()
                            self.sub_overlay.show() # Make sure it's visible
                        elif self.sub_overlay.isHidden():
                            self.sub_overlay.show() # Show if it was hidden
                        found_sub = True
                        break
                
                # If we are in a gap (no one talking), clear the text and hide
                if not found_sub:
                    if self.sub_overlay.isVisible():
                        self.sub_overlay.setText("")
                        self.sub_overlay.hide() # Hide completely to remove background box
                
                # Check AI Triggers
                if self.is_playing and self.next_ai_index < len(self.ai_segments):
                    seg = self.ai_segments[self.next_ai_index]
                    # Check if we reached the start time (with small tolerance)
                    # Use seconds for comparison
                    current_sec = self.current_msec / 1000.0
                    
                    if current_sec >= seg['start']:
                        # Play this segment
                        # print(f"Playing AI Segment: {seg['path']} at {current_sec}")
                        play_path = seg.get('preview_path') or seg['path']
                        self.ai_player.setMedia(QMediaContent(QUrl.fromLocalFile(play_path)))
                        self.ai_player.play()
                        self.current_ai_end = seg.get('_effective_end')
                        self.next_ai_index += 1

                if self.is_playing and self.current_ai_end is not None:
                    current_sec = self.current_msec / 1000.0
                    if current_sec >= self.current_ai_end + 0.02:
                        self.ai_player.stop()
                        self.current_ai_end = None
                
                if self.is_playing:
                    self.positionChanged.emit(self.current_msec)
            else:
                self.pause()
