from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
import os

class VideoProcessor:
    def __init__(self):
        pass

    def process_video(self, video_path, audio_segments, output_path, bg_music_volume=0.1, progress_callback=None):
        """
        video_path: Path to source video.
        audio_segments: List of dicts {'start': float, 'path': str}
        output_path: Path to save result.
        bg_music_volume: Volume of original audio (0.0 to 1.0).
        progress_callback: Function to call with progress updates (optional).
        """
        try:
            video = VideoFileClip(video_path)
            original_audio = video.audio
            
            # Adjust original audio volume
            if original_audio:
                original_audio = original_audio.with_volume_scaled(bg_music_volume)
            
            new_audio_clips = []
            if original_audio:
                new_audio_clips.append(original_audio)
            
            for seg in audio_segments:
                if os.path.exists(seg['path']):
                    # Create AudioFileClip
                    # timestamp is in seconds
                    clip = AudioFileClip(seg['path']).with_start(seg['start'])
                    new_audio_clips.append(clip)
            
            final_audio = CompositeAudioClip(new_audio_clips)
            
            # Set audio to video
            final_video = video.with_audio(final_audio)
            
            # Write output
            # logger=None suppresses standard moviepy output so we can handle progress if we wanted to hook into it deeper, 
            # but for now we'll let it print to console or use default.
            final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
            
            # Cleanup
            video.close()
            final_audio.close()
            return True, "Success"
            
        except Exception as e:
            return False, str(e)
