from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
import os

class VideoProcessor:
    def __init__(self):
        pass

    def process_video(self, video_path, audio_segments, output_path, original_volume=1.0, ai_volume=1.0, progress_callback=None):
        """
        video_path: Path to source video.
        audio_segments: List of dicts {'start': float, 'end': float|None, 'path': str}
        output_path: Path to save result.
        original_volume: Volume of original audio (0.0 to 1.0+). 0 means mute.
        ai_volume: Volume of AI audio (0.0 to 1.0+).
        """
        try:
            video = VideoFileClip(video_path)
            
            # Handle Original Audio
            original_audio = video.audio
            final_audio_clips = []

            if original_audio and original_volume > 0:
                original_audio = original_audio.with_volume_scaled(original_volume)
                final_audio_clips.append(original_audio)
            
            # Handle AI Audio Segments
            if ai_volume > 0:
                ai_clips = []
                for seg in audio_segments:
                    if os.path.exists(seg['path']):
                        # Create AudioFileClip
                        clip = AudioFileClip(seg['path'])

                        # Fit AI audio into subtitle window when end is provided
                        end = seg.get('end')
                        if end is not None:
                            target_duration = max(0.05, float(end) - float(seg['start']))
                            if clip.duration and clip.duration > target_duration:
                                clip = clip.subclip(0, target_duration)

                        clip = clip.with_start(seg['start'])
                        # Apply volume to AI clip
                        clip = clip.with_volume_scaled(ai_volume)
                        final_audio_clips.append(clip)
                        ai_clips.append(clip)
            
            if final_audio_clips:
                final_audio = CompositeAudioClip(final_audio_clips)
                final_video = video.with_audio(final_audio)
            else:
                # No audio at all
                final_video = video.without_audio()
            
            # Write output
            final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
            
            # Cleanup
            video.close()
            if 'final_audio' in locals():
                final_audio.close()
            if 'ai_clips' in locals():
                for c in ai_clips:
                    try:
                        c.close()
                    except Exception:
                        pass
            return True, "Success"
            
        except Exception as e:
            return False, str(e)
