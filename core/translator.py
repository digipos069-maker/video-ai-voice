from deep_translator import GoogleTranslator

class SubtitleTranslator:
    def __init__(self, target_lang='km'):
        self.translator = GoogleTranslator(source='auto', target=target_lang)

    def translate_subtitles(self, subtitles, progress_callback=None):
        """
        Translates a list of subtitle dictionaries.
        subtitles: List of {'index': int, 'start': float, 'end': float, 'text': str}
        """
        translated_subs = []
        total = len(subtitles)
        
        for i, sub in enumerate(subtitles):
            try:
                # Keep the structure, just change the text
                new_text = self.translator.translate(sub['text'])
                
                translated_subs.append({
                    'index': sub['index'],
                    'start': sub['start'],
                    'end': sub['end'],
                    'text': new_text,
                    'original_text': sub.get('original_text', sub['text']) # Preserve original
                })
            except Exception as e:
                print(f"Translation error at index {i}: {e}")
                # On error, keep original text to avoid losing sync
                translated_subs.append(sub)
            
            if progress_callback:
                progress_callback(int(((i + 1) / total) * 100))
                
        return translated_subs
