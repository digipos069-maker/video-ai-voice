from deep_translator import GoogleTranslator

try:
    print("Testing translation...")
    text = "Hello world"
    translated = GoogleTranslator(source='auto', target='km').translate(text)
    print(f"Original: {text}")
    print(f"Translated: {translated}")
except Exception as e:
    print(f"Error: {e}")
