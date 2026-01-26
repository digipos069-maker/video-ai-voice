import requests

def test_access():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    })

    # 1. Visit the episode page to get cookies
    ep_url = "https://www.dramaboxdb.com/ep/42000003486_kissing-the-wrong-brother/700215503_Episode-1"
    print(f"Visiting {ep_url}...")
    resp1 = session.get(ep_url)
    print(f"Page Status: {resp1.status_code}")
    print("Cookies:", session.cookies.get_dict())

    # 2. Try to fetch the m3u8
    # Note: The URL in the log was specific, but let's try to extract it dynamically or use the one from the log if valid
    # The log showed: https://hwzthls.dramaboxdb.com/.../700215503.720p.m3u8...
    # We will try a simplified test.
    
    # Let's try to re-extract using the logic to see if we get the same URL
    import re
    html = resp1.text
    m3u8_matches = re.findall(r'(https?://[^\s"\\]+\.m3u8[^\s"\\]*)', html)
    
    if not m3u8_matches:
        print("No m3u8 found in page.")
        return

    m3u8_url = m3u8_matches[0]
    print(f"Found m3u8: {m3u8_url}")

    # 3. Fetch m3u8 with Referer
    headers = {
        "Referer": ep_url
    }
    print("Fetching m3u8...")
    resp2 = session.get(m3u8_url, headers=headers)
    print(f"M3U8 Status: {resp2.status_code}")
    
    if resp2.status_code == 200:
        print("Success! Content preview:")
        print(resp2.text[:200])
    else:
        print("Failed.")
        print(resp2.text)

if __name__ == "__main__":
    test_access()
