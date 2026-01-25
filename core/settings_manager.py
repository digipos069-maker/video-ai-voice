import json
import os

SETTINGS_FILE = "settings.json"

class SettingsManager:
    @staticmethod
    def load_settings():
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    @staticmethod
    def save_setting(key, value):
        settings = SettingsManager.load_settings()
        settings[key] = value
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)

    @staticmethod
    def get_setting(key, default=None):
        settings = SettingsManager.load_settings()
        return settings.get(key, default)
