import asyncio
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

    async def generate_batch(self):
        audio_segments = []
        total = len(self.subtitles)
        
        for i, sub in enumerate(self.subtitles):
            if not self.is_running:
                break
            
            filename = f"segment_{sub['index']}.mp3"
            output_path = os.path.join(self.output_dir, filename)
            
            # Use the internal async method of the generator directly if possible,
            # but since AudioGenerator.generate wraps asyncio.run, we should bypass it 
            # or expose the async method.
            # To avoid changing core logic too much, we will call the async logic directly here.
            try:
                # We need to access the async method _generate_audio from the generator instance
                # Since it is 'protected', we'll access it or we should make it public.
                # Accessing protected member for stability fix.
                await self.generator._generate_audio(sub['text'], self.voice, output_path)
                
                audio_segments.append({
                    'start': sub['start'],
                    'path': output_path
                })
            except Exception as e:
                print(f"Error generating segment {i}: {e}")
                # We continue even if one fails, or we could emit error.
            
            self.progress.emit(int(((i + 1) / total) * 100))
            
        return audio_segments

    def run(self):
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            audio_segments = loop.run_until_complete(self.generate_batch())
            loop.close()
            
            self.finished.emit(audio_segments)
        except Exception as e:
            self.error.emit(str(e))

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
