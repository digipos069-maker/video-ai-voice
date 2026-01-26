import requests
import re
import json

url = "https://www.goodshort.com/episodes/eng-dub-war-god-s-redemption-a-father-s-promise-31001266638"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.goodshort.com/'
}

try:
    print(f"Fetching {url}...")
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    html = response.text
    
    # 1. Look for m3u8
    m3u8_matches = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
    print(f"Direct m3u8 matches: {len(m3u8_matches)}")
    for m in m3u8_matches[:3]:
        print(f" - {m}")
        
    # 2. Look for JSON data (Next.js props or similar)
    # Often in <script id="__NEXT_DATA__" type="application/json">
    next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if next_data_match:
        print("Found __NEXT_DATA__")
        data = json.loads(next_data_match.group(1))
        # Navigate to find useful info
        # Just printing keys to understand structure
        print("Keys in props:", data.get('props', {}).keys())
        
        # Try to find episode list
        try:
            page_props = data.get('props', {}).get('pageProps', {})
            # Depending on structure, it might be in 'episodeList' or 'detail'
            print("Keys in pageProps:", page_props.keys())
            
            if 'episodeList' in page_props:
                print(f"Found episodeList with {len(page_props['episodeList'])} items")
                print("First item:", page_props['episodeList'][0])
                
        except Exception as e:
            print(f"Error parsing JSON data: {e}")
            
    else:
        print("No __NEXT_DATA__ found.")

except Exception as e:
    print(f"Error: {e}")
