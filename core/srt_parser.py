import re

def parse_srt(file_path):
    """
    Parses an SRT file and returns a list of subtitles.
    Each subtitle is a dict: {'index': int, 'start': float, 'end': float, 'text': str}
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex to find blocks.
    # Timestamp format: 00:00:00,000
    pattern = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:(?!\n\n).)*)', re.DOTALL)
    
    matches = pattern.findall(content)
    subtitles = []

    for match in matches:
        index = int(match[0])
        start_str = match[1]
        end_str = match[2]
        text = match[3].strip()

        subtitles.append({
            'index': index,
            'start': timestamp_to_seconds(start_str),
            'end': timestamp_to_seconds(end_str),
            'text': text
        })
    
    return subtitles

def timestamp_to_seconds(ts):
    """Converts 00:00:00,000 to seconds (float)."""
    hours, minutes, seconds = ts.split(':')
    seconds, millis = seconds.split(',')
    
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000.0
    return total_seconds
