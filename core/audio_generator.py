import asyncio
import edge_tts
import os

class AudioGenerator:
    def __init__(self, output_dir="temp_audio"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    async def _generate_audio(self, text, voice, output_file):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)

    def generate(self, text, voice, filename):
        """
        Generates audio for the given text using the specified voice.
        Returns the path to the generated file.
        """
        output_path = os.path.join(self.output_dir, filename)
        try:
            asyncio.run(self._generate_audio(text, voice, output_path))
            return output_path
        except Exception as e:
            print(f"Error generating audio: {e}")
            return None

    @staticmethod
    async def _get_voices():
        voices = await edge_tts.list_voices()
        return voices

    @staticmethod
    def get_available_voices():
        """Returns a list of available voices."""
        return asyncio.run(AudioGenerator._get_voices())

# Helper to clean up temp files
def cleanup_temp_audio(directory="temp_audio"):
    if os.path.exists(directory):
        for f in os.listdir(directory):
            os.remove(os.path.join(directory, f))
        os.rmdir(directory)
