from PyQt5.QtCore import QThread, pyqtSignal
from core.audio_generator import AudioGenerator
from core.video_processor import VideoProcessor
from core.transcriber import Transcriber
import os

class TranscriptionWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path
        self.transcriber = Transcriber("base")

    def run(self):
        try:
            segments = self.transcriber.transcribe_video(self.video_path)
            self.finished.emit(segments)
        except Exception as e:
            self.error.emit(str(e))

class AudioGenerationWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list) # Returns list of audio segments
    error = pyqtSignal(str)

    def __init__(self, subtitles, voice, output_dir):
        super().__init__()
        self.subtitles = subtitles
        self.voice = voice
        self.output_dir = output_dir
        self.generator = AudioGenerator(output_dir)
        self.is_running = True

    def run(self):
        audio_segments = []
        total = len(self.subtitles)
        
        for i, sub in enumerate(self.subtitles):
            if not self.is_running:
                break
            
            filename = f"segment_{sub['index']}.mp3"
            path = self.generator.generate(sub['text'], self.voice, filename)
            
            if path:
                audio_segments.append({
                    'start': sub['start'],
                    'path': path
                })
            else:
                self.error.emit(f"Failed to generate audio for subtitle {sub['index']}")
            
            self.progress.emit(int(((i + 1) / total) * 100))
        
        self.finished.emit(audio_segments)

    def stop(self):
        self.is_running = False

class VideoExportWorker(QThread):
    finished = pyqtSignal(bool, str)
    
    def __init__(self, video_path, audio_segments, output_path, bg_volume):
        super().__init__()
        self.video_path = video_path
        self.audio_segments = audio_segments
        self.output_path = output_path
        self.bg_volume = bg_volume
        self.processor = VideoProcessor()

    def run(self):
        success, message = self.processor.process_video(
            self.video_path,
            self.audio_segments,
            self.output_path,
            self.bg_volume
        )
        self.finished.emit(success, message)
