import requests
import re

url = "https://www.goodshort.com/episodes/eng-dub-war-god-s-redemption-a-father-s-promise-31001266638"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.goodshort.com/'
}

resp = requests.get(url, headers=headers)
html = resp.text

print("--- Context around 'm3u8' ---")
# Find index of first m3u8
idx = html.find(".m3u8")
if idx != -1:
    start = max(0, idx - 500)
    end = min(len(html), idx + 500)
    print(html[start:end])
else:
    print("No m3u8 found string literal.")

print("\n--- Context around 'Episode' ---")
# Find patterns like <a href=\"...\">Episode 1</a>
# We'll just print a chunk around the first occurrence of "Episode 1"
idx_ep = html.find("Episode 1")
if idx_ep != -1:
    start = max(0, idx_ep - 500)
    end = min(len(html), idx_ep + 500)
    print(html[start:end])
