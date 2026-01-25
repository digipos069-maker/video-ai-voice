import whisper
import os
import subprocess
import imageio_ffmpeg
import traceback
import sys
import torch

def log_debug(message):
    """Writes debug info to a file since the console might close."""
    with open("debug_log.txt", "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print(message)

class Transcriber:
    def __init__(self, model_name="base"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            log_debug("Initializing OpenAI Whisper Model...")
            try:
                # Force CPU to avoid any potential CUDA/DLL issues that aren't properly set up
                self._model = whisper.load_model(self.model_name, device="cpu")
                log_debug("Whisper Model loaded (CPU).")
            except Exception as e:
                log_debug(f"FATAL: Could not load model. Error: {e}")
                raise e
        return self._model

    def transcribe_video(self, video_path, output_srt=None):
        temp_audio = "temp_transcription_audio.mp3"
        
        # Ensure clean state
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except:
                pass

        try:
            log_debug(f"Starting audio extraction for: {video_path}")
            
            # Get the ffmpeg binary path provided by imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            
            # Use direct subprocess call
            cmd = [
                ffmpeg_exe,
                "-i", video_path,
                "-vn", # No video
                "-acodec", "libmp3lame",
                "-q:a", "4",
                "-y", # Overwrite
                temp_audio
            ]
            
            # Run silently
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                log_debug(f"FFmpeg failed: {result.stderr}")
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
                
            log_debug("Audio extracted successfully.")

            if not os.path.exists(temp_audio):
                raise RuntimeError("Audio extraction appeared to succeed but file is missing.")

            log_debug("Starting transcription...")
            # Run transcription
            # OpenAI Whisper's transcribe method
            result = self.model.transcribe(temp_audio, fp16=False) # fp16=False is crucial for CPU
            
            segments = []
            for i, seg in enumerate(result['segments']):
                segments.append({
                    'index': i + 1,
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': seg['text'].strip()
                })
            
            log_debug(f"Transcription complete. Segments: {len(segments)}")
            
            # Explicit cleanup
            del self._model
            self._model = None
            
            return segments
            
        except Exception as e:
            log_debug(f"CRITICAL ERROR in transcribe_video: {e}")
            log_debug(traceback.format_exc())
            raise e
            
        finally:
            if os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except:
                    pass

def segments_to_srt(segments):
    srt_lines = []
    for seg in segments:
        srt_lines.append(str(seg['index']))
        srt_lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        srt_lines.append(seg['text'])
        srt_lines.append("")
    return "\n".join(srt_lines)

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"