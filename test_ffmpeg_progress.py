import subprocess
import re
import sys
import time

def parse_time(time_str):
    """Converts HH:MM:SS.mm to seconds"""
    try:
        parts = time_str.split(':')
        h = int(parts[0])
        m = int(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s
    except:
        return 0

def test_ffmpeg():
    # We need a valid URL to test. 
    # Using a test source or just checking the logic with a mocked output generator would be safer/faster.
    # But let's try to mock the *reading* logic.
    
    print("Testing FFmpeg progress parsing logic...")
    
    # Mock output of ffmpeg
    mock_output = [
        "Duration: 00:01:30.50, start: 0.000000, bitrate: 1000 kb/s",
        "something else...",
        "frame=  100 fps= 25 q=-1.0 size=    1024kB time=00:00:10.00 bitrate= 838.9kbits/s speed=22.6x",
        "frame=  200 fps= 25 q=-1.0 size=    2048kB time=00:00:20.00 bitrate= 838.9kbits/s speed=22.6x",
        "frame=  900 fps= 25 q=-1.0 size=    9000kB time=00:01:30.00 bitrate= 838.9kbits/s speed=22.6x",
    ]
    
    duration = 0
    
    for line in mock_output:
        line = line.strip()
        
        # 1. Parse Duration
        if "Duration:" in line:
            # Duration: 00:01:30.50, ...
            match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d{2})", line)
            if match:
                duration = parse_time(match.group(1))
                print(f"Found Duration: {duration} seconds")
        
        # 2. Parse Progress
        if "time=" in line:
            # time=00:00:10.00
            match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
            if match:
                current_time = parse_time(match.group(1))
                if duration > 0:
                    percent = (current_time / duration) * 100
                    print(f"Progress: {percent:.1f}% ({current_time}s / {duration}s)")

if __name__ == "__main__":
    test_ffmpeg()
