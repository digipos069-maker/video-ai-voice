import sys
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTableWidget, 
                             QTableWidgetItem, QTabWidget, QHeaderView, QSlider, 
                             QComboBox, QMessageBox, QProgressBar, QGroupBox, QLineEdit,
                             QGridLayout, QCheckBox, QStyle)
from PyQt5.QtCore import Qt, QUrl, QTime
from PyQt5.QtGui import QIcon

from ui.styles import STYLESHEET, PRIMARY_COLOR
from ui.workers import AudioGenerationWorker, VideoExportWorker, TranscriptionWorker, TranslationWorker
from ui.video_player import VideoPlayer
from core.srt_parser import parse_srt
from core.audio_generator import AudioGenerator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video AI Voiceover Tool")
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)

        # State
        self.video_path = None
        self.srt_path = None
        self.subtitles = []
        self.generated_audio_segments = []
        self.output_dir = os.path.join(os.getcwd(), "temp_audio")
        self._active_threads = [] # Keep references to threads
        
        # UI Setup
        self.init_ui()
        self.load_voices()

    def init_ui(self):
        # Main Container
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # Tab 1: Editor
        self.editor_tab = QWidget()
        self.setup_editor_tab()
        self.tabs.addTab(self.editor_tab, "Editor")

        # Tab 2: Settings
        self.settings_tab = QWidget()
        self.setup_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")
        
        # Apply cursors to all buttons
        self.set_cursors()

    def set_cursors(self):
        """Recursively sets pointing hand cursor for all buttons."""
        buttons = self.findChildren(QPushButton)
        for btn in buttons:
            btn.setCursor(Qt.PointingHandCursor)
            
        # Also set for ComboBoxes and CheckBoxes
        for widget in self.findChildren((QComboBox, QCheckBox)):
            widget.setCursor(Qt.PointingHandCursor)

    def create_track_widget(self, label_text):
        """Creates a track widget with label, volume slider, and mute button."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 5, 0, 5)

        # Label
        lbl = QLabel(label_text)
        lbl.setFixedWidth(120)
        
        # Slider
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(100)
        
        # Mute Checkbox
        chk_mute = QCheckBox("Mute")
        
        # Logic to enable/disable slider and emit changes
        chk_mute.stateChanged.connect(lambda: slider.setEnabled(not chk_mute.isChecked()))
        
        layout.addWidget(lbl)
        layout.addWidget(slider)
        layout.addWidget(chk_mute)
        
        container.slider = slider
        container.chk_mute = chk_mute
        return container

    def setup_editor_tab(self):
        layout = QHBoxLayout(self.editor_tab)

        # --- LEFT PANEL ---
        left_panel = QVBoxLayout()
        
        # 1. Video Player
        self.video_player = VideoPlayer()
        self.video_player.stateChanged.connect(self.media_state_changed)
        self.video_player.positionChanged.connect(self.position_changed)
        self.video_player.durationChanged.connect(self.duration_changed)
        self.video_player.importRequested.connect(self.load_video) # Connect click-to-import
        left_panel.addWidget(self.video_player)

        # 2. Player Controls
        controls_layout = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_play.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_play.clicked.connect(self.play_video)
        self.slider_seek = QSlider(Qt.Horizontal)
        self.slider_seek.sliderMoved.connect(self.set_position)
        
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.slider_seek)
        left_panel.addLayout(controls_layout)

        # --- Audio Tracks (New) ---
        tracks_group = QGroupBox("Audio Tracks")
        tracks_layout = QVBoxLayout()
        
        self.widget_orig_track = self.create_track_widget("Original Audio")
        self.widget_orig_track.setVisible(False) # Hidden initially
        
        # Connect Volume Control
        self.widget_orig_track.slider.valueChanged.connect(self.video_player.set_orig_volume)
        self.widget_orig_track.chk_mute.stateChanged.connect(
            lambda state: self.video_player.set_orig_volume(0 if state else self.widget_orig_track.slider.value())
        )
        
        tracks_layout.addWidget(self.widget_orig_track)
        
        self.widget_ai_track = self.create_track_widget("AI Voiceover")
        self.widget_ai_track.setVisible(False) # Hidden initially
        
        # Connect AI Volume Control
        self.widget_ai_track.slider.valueChanged.connect(self.video_player.set_ai_volume)
        self.widget_ai_track.chk_mute.stateChanged.connect(
            lambda state: self.video_player.set_ai_volume(0 if state else self.widget_ai_track.slider.value())
        )
        
        tracks_layout.addWidget(self.widget_ai_track)
        
        tracks_group.setLayout(tracks_layout)
        left_panel.addWidget(tracks_group)

        # Spacer to push buttons to bottom
        left_panel.addStretch()

        # 3. Import Buttons (Moved to Bottom)
        actions_layout = QHBoxLayout()
        self.btn_load_video = QPushButton("Import Video")
        self.btn_load_video.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.btn_load_video.clicked.connect(self.load_video)
        
        self.btn_load_srt = QPushButton("Import Subtitles")
        self.btn_load_srt.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        self.btn_load_srt.clicked.connect(self.load_subtitles)

        self.btn_export_srt = QPushButton("Export Subtitles")
        self.btn_export_srt.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_export_srt.clicked.connect(self.save_subtitles)
        self.btn_export_srt.setEnabled(False)

        self.btn_auto_srt = QPushButton("Auto-Generate")
        self.btn_auto_srt.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        self.btn_auto_srt.clicked.connect(self.auto_generate_subtitles)
        self.btn_auto_srt.setEnabled(False)

        self.btn_translate = QPushButton("Translate (Khmer)")
        self.btn_translate.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton)) # Apply/Check icon
        self.btn_translate.clicked.connect(self.translate_subtitles)
        self.btn_translate.setEnabled(False)
        
        actions_layout.addWidget(self.btn_load_video)
        actions_layout.addWidget(self.btn_load_srt)
        actions_layout.addWidget(self.btn_export_srt)
        actions_layout.addWidget(self.btn_auto_srt)
        actions_layout.addWidget(self.btn_translate)
        left_panel.addLayout(actions_layout)
        
        layout.addLayout(left_panel, stretch=2)

        # --- RIGHT PANEL ---
        right_panel = QVBoxLayout()
        
        # 1. Subtitle Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Start", "End", "Text"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        right_panel.addWidget(self.table)

        # 2. Generation Controls
        gen_group = QGroupBox("Process")
        gen_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        gen_layout.addWidget(self.progress_bar)

        self.btn_generate = QPushButton("Generate AI Voice")
        self.btn_generate.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_generate.clicked.connect(self.generate_voice)
        self.btn_generate.setEnabled(False)
        gen_layout.addWidget(self.btn_generate)

        self.btn_export = QPushButton("Export Final Video")
        self.btn_export.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.btn_export.clicked.connect(self.export_video)
        self.btn_export.setEnabled(False)
        gen_layout.addWidget(self.btn_export)

        gen_group.setLayout(gen_layout)
        right_panel.addWidget(gen_group)

        layout.addLayout(right_panel, stretch=1)

    def setup_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        
        # Voice Settings
        voice_group = QGroupBox("Voice Settings")
        voice_layout = QGridLayout()
        
        voice_layout.addWidget(QLabel("Select Voice:"), 0, 0)
        self.combo_voices = QComboBox()
        voice_layout.addWidget(self.combo_voices, 0, 1)

        voice_layout.addWidget(QLabel("Background Music Volume (0.0 - 1.0):"), 1, 0)
        self.slider_vol = QSlider(Qt.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(10) # 0.1 default
        voice_layout.addWidget(self.slider_vol, 1, 1)

        voice_group.setLayout(voice_layout)
        layout.addWidget(voice_group)
        layout.addStretch()

    def load_voices(self):
        # For now, load some hardcoded popular Edge-TTS voices to avoid async blocking on startup
        # ideally we fetch this, but for speed:
        common_voices = [
            "en-US-AriaNeural", 
            "en-US-GuyNeural", 
            "en-US-JennyNeural",
            "en-GB-SoniaNeural",
            "en-GB-RyanNeural",
            "km-KH-PisethNeural",   # Khmer Male
            "km-KH-SreymomNeural"   # Khmer Female
        ]
        self.combo_voices.addItems(common_voices)

    # --- Video Player Slots ---
    def play_video(self):
        if self.video_player.is_playing:
            self.video_player.pause()
        else:
            self.video_player.play()

    def media_state_changed(self, is_playing):
        if is_playing:
            self.btn_play.setText("Pause")
        else:
            self.btn_play.setText("Play")

    def position_changed(self, position):
        # Block signals to prevent feedback loop while seeking manually
        self.slider_seek.blockSignals(True)
        self.slider_seek.setValue(position)
        self.slider_seek.blockSignals(False)

    def duration_changed(self, duration):
        self.slider_seek.setRange(0, duration)

    def set_position(self, position):
        self.video_player.set_position(position)

    # --- File Loading ---
    def load_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov)")
        if path:
            success, err = self.video_player.load_video(path)
            if success:
                self.video_path = path
                self.btn_play.setEnabled(True)
                self.widget_orig_track.setVisible(True) # Show Original Track
                self.check_enable_generate()
            else:
                QMessageBox.critical(self, "Error", err)

    def load_subtitles(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Subtitles", "", "SRT Files (*.srt)")
        if path:
            self.srt_path = path
            self.subtitles = parse_srt(path)
            self.populate_table()
            self.check_enable_generate()

    def populate_table(self):
        self.table.setRowCount(len(self.subtitles))
        for i, sub in enumerate(self.subtitles):
            self.table.setItem(i, 0, QTableWidgetItem(self.format_time(sub['start'])))
            self.table.setItem(i, 1, QTableWidgetItem(self.format_time(sub['end'])))
            self.table.setItem(i, 2, QTableWidgetItem(sub['text']))
            
        # Update Video Player
        self.video_player.set_subtitles(self.subtitles)

    def format_time(self, seconds):
        return QTime(0, 0).addMSecs(int(seconds * 1000)).toString("mm:ss.zzz")

    def check_enable_generate(self):
        if self.video_path:
            self.btn_auto_srt.setEnabled(True)
        if self.subtitles:
            self.btn_export_srt.setEnabled(True)
            self.btn_translate.setEnabled(True)
        if self.video_path and self.subtitles:
            self.btn_generate.setEnabled(True)

    def translate_subtitles(self):
        print("Translate button clicked.")
        if not self.subtitles:
            print("No subtitles to translate.")
            return
            
        print(f"Starting translation for {len(self.subtitles)} lines...")
        self.btn_translate.setEnabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        worker = TranslationWorker(self.subtitles, target_lang='km')
        worker.progress.connect(self.progress_bar.setValue)
        worker.finished.connect(self.on_translation_finished)
        worker.error.connect(lambda err: QMessageBox.critical(self, "Error", err))
        worker.finished.connect(lambda: self._active_threads.remove(worker) if worker in self._active_threads else None)
        
        self._active_threads.append(worker)
        worker.start()

    def on_translation_finished(self, translated_subs):
        self.subtitles = translated_subs
        self.populate_table()
        self.btn_translate.setEnabled(True)
        self.progress_bar.setValue(100)
        
        # Auto-select Khmer voice to prevent errors
        index = self.combo_voices.findText("km-KH-PisethNeural")
        if index != -1:
            self.combo_voices.setCurrentIndex(index)
            
        QMessageBox.information(self, "Success", "Translation to Khmer complete!\nVoice automatically set to 'km-KH-PisethNeural'.")

    def save_subtitles(self):
        if not self.subtitles:
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Subtitles", "", "SRT Files (*.srt)")
        if path:
            from core.transcriber import segments_to_srt
            srt_content = segments_to_srt(self.subtitles)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            QMessageBox.information(self, "Success", f"Subtitles saved to {path}")

    # --- Logic ---
    def auto_generate_subtitles(self):
        if not self.video_path:
            return

        self.btn_auto_srt.setEnabled(False)
        self.progress_bar.setRange(0, 0) # Loading...
        
        worker = TranscriptionWorker(self.video_path)
        worker.finished.connect(self.on_transcription_finished)
        worker.error.connect(lambda err: QMessageBox.critical(self, "Error", err))
        # Fix: Accept the 'segments' argument even if we don't use it in this lambda
        worker.finished.connect(lambda segments: self._active_threads.remove(worker) if worker in self._active_threads else None)
        
        self._active_threads.append(worker)
        worker.start()

    def on_transcription_finished(self, segments):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.btn_auto_srt.setEnabled(True)
        
        self.subtitles = segments
        self.populate_table()
        self.check_enable_generate()
        QMessageBox.information(self, "Success", "Subtitles extracted from video successfully!")

    def generate_voice(self):
        voice = self.combo_voices.currentText()
        
        self.thread_audio = AudioGenerationWorker(self.subtitles, voice, self.output_dir)
        self.thread_audio.progress.connect(self.progress_bar.setValue)
        self.thread_audio.finished.connect(self.on_audio_generated)
        self.thread_audio.error.connect(lambda err: QMessageBox.critical(self, "Error", err))
        
        self.btn_generate.setEnabled(False)
        self.thread_audio.start()

    def on_audio_generated(self, segments):
        self.generated_audio_segments = segments
        
        # Load segments into player for preview
        self.video_player.load_ai_segments(segments)
        
        self.btn_generate.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.widget_ai_track.setVisible(True) # Show AI Track
        QMessageBox.information(self, "Success", "Audio generation complete! You can now export the video.")

    def export_video(self):
        output_path, _ = QFileDialog.getSaveFileName(self, "Save Video", "", "MP4 Files (*.mp4)")
        if output_path:
            # Calculate Volumes from new widgets
            if self.widget_orig_track.chk_mute.isChecked():
                vol_orig = 0.0
            else:
                vol_orig = self.widget_orig_track.slider.value() / 100.0

            if self.widget_ai_track.chk_mute.isChecked():
                vol_ai = 0.0
            else:
                vol_ai = self.widget_ai_track.slider.value() / 100.0
            
            self.thread_export = VideoExportWorker(
                self.video_path, 
                self.generated_audio_segments, 
                output_path, 
                vol_orig, 
                vol_ai
            )
            self.thread_export.finished.connect(self.on_export_finished)
            
            self.progress_bar.setValue(0) 
            self.progress_bar.setRange(0, 0) # Infinite loading
            self.btn_export.setEnabled(False)
            self.thread_export.start()

    def on_export_finished(self, success, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.btn_export.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Success", f"Video exported successfully!")
        else:
            QMessageBox.critical(self, "Error", f"Export failed:\n{message}")
