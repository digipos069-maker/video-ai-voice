import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
from core.audio_generator import AudioGenerator
from core.video_processor import VideoProcessor
from core.transcriber import Transcriber, log_debug
from core.translator import SubtitleTranslator
import os
import traceback

class TranslationWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, subtitles, target_lang='km'):
        super().__init__()
        self.subtitles = subtitles
        self.target_lang = target_lang
        self.translator = SubtitleTranslator(target_lang)

    def run(self):
        try:
            log_debug(f"Starting translation to {self.target_lang}...")
            translated = self.translator.translate_subtitles(
                self.subtitles, 
                lambda p: self.progress.emit(p)
            )
            self.finished.emit(translated)
            log_debug("Translation complete.")
        except Exception as e:
            err_msg = f"Translation failed: {str(e)}"
            log_debug(err_msg)
            self.error.emit(str(e))

class TranscriptionWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, video_path):
        super().__init__()
        self.video_path = video_path

    def run(self):
        try:
            log_debug("Worker thread started.")
            self.transcriber = Transcriber("base")
            segments = self.transcriber.transcribe_video(self.video_path)
            self.finished.emit(segments)
            log_debug("Worker thread finished successfully.")
        except Exception as e:
            err_msg = f"Transcription failed: {str(e)}"
            log_debug(err_msg)
            log_debug(traceback.format_exc())
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
            
            try:
                await self.generator._generate_audio(sub['text'], self.voice, output_path)
                
                audio_segments.append({
                    'start': sub['start'],
                    'path': output_path
                })
            except Exception as e:
                print(f"Error generating segment {i}: {e}")
            
            self.progress.emit(int(((i + 1) / total) * 100))
            
        return audio_segments

    def run(self):
        try:
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
    
    def __init__(self, video_path, audio_segments, output_path, original_volume, ai_volume):
        super().__init__()
        self.video_path = video_path
        self.audio_segments = audio_segments
        self.output_path = output_path
        self.original_volume = original_volume
        self.ai_volume = ai_volume
        self.processor = VideoProcessor()

    def run(self):
        success, message = self.processor.process_video(
            self.video_path,
            self.audio_segments,
            self.output_path,
            self.original_volume,
            self.ai_volume
        )
        self.finished.emit(success, message)
