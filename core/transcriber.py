from faster_whisper import WhisperModel
import os
from moviepy import VideoFileClip

class Transcriber:
    def __init__(self, model_size="base"):
        """
        model_size: "tiny", "base", "small", "medium", "large"
        'base' is a good balance for speed and accuracy.
        """
        self.model_size = model_size
        self._model = None

    @property
    def model(self):
        if self._model is None:
            # Run on CPU with INT8 quantization for maximum compatibility and speed on standard machines
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe_video(self, video_path, output_srt=None):
        """
        Transcribes the video and returns a list of subtitle segments.
        """
        # 1. Extract audio to a temporary file
        temp_audio = "temp_transcription_audio.mp3"
        
        try:
            video = VideoFileClip(video_path)
            if video.audio is None:
                raise ValueError("Video has no audio track.")
                
            video.audio.write_audiofile(temp_audio, logger=None)
            video.close()

            # 2. Transcribe
            # faster-whisper returns a generator, so we iterate over it
            segments, info = self.model.transcribe(temp_audio, beam_size=5)
            
            result_segments = []
            for i, seg in enumerate(segments):
                result_segments.append({
                    'index': i + 1,
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text.strip()
                })

            return result_segments
            
        except Exception as e:
            raise e
            
        finally:
            # 3. Cleanup audio
            if os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except:
                    pass

def segments_to_srt(segments):
    """Converts segments list to SRT string format."""
    srt_lines = []
    for seg in segments:
        srt_lines.append(str(seg['index']))
        srt_lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        srt_lines.append(seg['text'])
        srt_lines.append("") # Empty line between blocks
    return "\n".join(srt_lines)

def format_timestamp(seconds):
    """Converts seconds to 00:00:00,000 format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"