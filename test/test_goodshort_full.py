import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.goodshort_downloader import GoodShortDownloader
import json
import os

def test_fetch():
    url = "https://www.goodshort.com/episodes/eng-dub-war-god-s-redemption-a-father-s-promise-31001266638"
    downloader = GoodShortDownloader()
    
    print(f"Fetching info for: {url}")
    try:
        info = downloader.fetch_drama_info(url)
        print(f"Title: {info['title']}")
        print(f"Found {len(info['episodes'])} episodes.")
        
        if info['episodes']:
            print("First 3 episodes:")
            for ep in info['episodes'][:3]:
                print(f" - {ep['title']} (Video URL: {'Yes' if ep.get('video_url') else 'No'})")
            
            print("Last 3 episodes:")
            for ep in info['episodes'][-3:]:
                print(f" - {ep['title']} (Video URL: {'Yes' if ep.get('video_url') else 'No'})")
                
            # Check how many have video URLs
            locked_count = sum(1 for ep in info['episodes'] if not ep.get('video_url'))
            print(f"Locked episodes (no direct video URL): {locked_count}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_fetch()
