import whisper
import os
import subprocess
import imageio_ffmpeg
import traceback
import sys
import torch
import numpy as np

def log_debug(message):
    """Writes debug info to a file since the console might close."""
    with open("debug_log.txt", "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print(message)

# --- Monkey-patch Whisper to use imageio_ffmpeg ---
# This fixes the "WinError 2" by ensuring Whisper finds ffmpeg
def custom_load_audio(file: str, sr: int = 16000):
    """
    Open an audio file and read as mono waveform, resampling as necessary.
    Based on whisper.audio.load_audio but uses explicit ffmpeg path.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    cmd = [
        ffmpeg_exe,
        "-nostdin",
        "-threads", "0",
        "-i", file,
        "-f", "s16le",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        "-ar", str(sr),
        "-"
    ]
    
    try:
        out = subprocess.run(cmd, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to load audio: {e.stderr.decode()}") from e

    return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0

# Apply the patch
whisper.audio.load_audio = custom_load_audio
# --------------------------------------------------

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
        try:
            log_debug("Starting transcription...")
            # Run transcription
            # OpenAI Whisper's transcribe method
            result = self.model.transcribe(video_path, fp16=False) # fp16=False is crucial for CPU
            
            segments = []
            for i, seg in enumerate(result['segments']):
                text = seg['text'].strip()
                segments.append({
                    'index': i + 1,
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': text,
                    'original_text': text
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
