import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

class GoodShortDownloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.goodshort.com/'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.base_url = None

    def set_cookie(self, cookie_str):
        """Sets the Cookie header for requests."""
        if cookie_str:
            self.headers['Cookie'] = cookie_str
            self.session.headers.update({'Cookie': cookie_str})

    def fetch_drama_info(self, url):
        """
        Fetches drama title and list of episodes from the given URL.
        """
        try:
            self.base_url = url
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            drama_title = "Unknown Drama"
            episodes = []
            
            # Strategy 1: JSON-LD (Schema.org)
            # Good for basic info, often misses deep links for locked content
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict): items = [data]
                    elif isinstance(data, list): items = data
                    else: continue
                    
                    for item in items:
                        if item.get('@type') == 'ItemList':
                            for el in item.get('itemListElement', []):
                                if el.get('@type') == 'VideoObject':
                                    self._parse_video_object(el, episodes)
                        elif item.get('@type') == 'VideoObject':
                            self._parse_video_object(item, episodes)
                except: pass

            # Strategy 2: window.__INITIAL_STATE__ (Internal React State)
            # Often contains the true state, including m3u8Path for unlocked episodes
            initial_state_match = re.search(r'window\.__INITIAL_STATE__=(.*?);?\s*(\n|<)', html)
            if not initial_state_match:
                 # Try greedy match if simple one fails
                 initial_state_match = re.search(r'window\.__INITIAL_STATE__=(.*)', html)

            if initial_state_match:
                try:
                    # We need a robust JSON extractor as regex is brittle
                    json_str = self._extract_balanced_json(html, initial_state_match.start(1))
                    if json_str:
                        state_data = json.loads(json_str)
                        self._parse_initial_state(state_data, episodes)
                except Exception as e:
                    print(f"Error parsing INITIAL_STATE: {e}")

            # Deduplicate episodes based on ID or Title
            unique_episodes = {}
            for ep in episodes:
                # Use title as key if id is not unique enough, or just id
                key = ep['title']
                if key not in unique_episodes:
                    unique_episodes[key] = ep
                else:
                    # Merge info: if new one has video_url and old one didn't, update
                    if ep.get('video_url') and not unique_episodes[key].get('video_url'):
                        unique_episodes[key]['video_url'] = ep['video_url']
            
            episodes = list(unique_episodes.values())

            # If title is still unknown, try to get it from the first episode
            if episodes:
                first_title = episodes[0]['title']
                if " - EP" in first_title:
                    drama_title = first_title.split(" - EP")[0]
                else:
                    drama_title = first_title

            # Sort by episode number
            def extract_ep_num(ep):
                # Look for "EP X" or just numbers
                match = re.search(r'(?:EP|Episode)\s?(\d+)', ep['title'], re.IGNORECASE)
                if match:
                    return int(match.group(1))
                return 999999
            
            episodes.sort(key=extract_ep_num)

            return {
                'title': drama_title,
                'episodes': episodes
            }

        except Exception as e:
            raise Exception(f"Failed to fetch GoodShort info: {str(e)}")

    def _extract_balanced_json(self, text, start_index):
        """Helper to extract JSON object by counting braces"""
        stack = 0
        found_start = False
        for i in range(start_index, len(text)):
            char = text[i]
            if char == '{':
                stack += 1
                found_start = True
            elif char == '}':
                stack -= 1
                if found_start and stack == 0:
                    return text[start_index:i+1]
        return None

    def _parse_initial_state(self, data, episodes_list):
        """Parses the React state to find chapterList"""
        def find_key(obj, target_key):
            if isinstance(obj, dict):
                if target_key in obj: return obj[target_key]
                for k, v in obj.items():
                    res = find_key(v, target_key)
                    if res: return res
            elif isinstance(obj, list):
                for item in obj:
                    res = find_key(item, target_key)
                    if res: return res
            return None

        chapters = find_key(data, 'chapterList')
        if chapters and isinstance(chapters, list):
            # We found the internal chapter list!
            # It usually contains 'chapterName' (e.g. "001"), 'm3u8Path', etc.
            
            # We need to map these to our existing episodes or add new ones
            # The 'title' in JSON-LD is "[ENG DUB] ... - EP 1"
            # Here 'chapterName' might be "001"
            
            # Let's try to construct a matching title or just use what we have
            # If we already have episodes from JSON-LD, we try to enrich them.
            
            # First, check if we have a "bookName" or similar in data to prefix titles
            # But 'data' is huge.
            
            for ch in chapters:
                ep_num_str = ch.get('chapterName', '') # e.g. "001"
                try:
                    ep_num = int(ep_num_str)
                    clean_title = f"EP {ep_num}"
                except:
                    clean_title = ep_num_str
                
                video_url = ch.get('m3u8Path')
                
                # Check if this chapter is already in our list (fuzzy match by number)
                found = False
                for existing in episodes_list:
                    # Check if "EP {ep_num}" is in the existing title
                    if f"EP {ep_num}" in existing['title'] or f"Episode {ep_num}" in existing['title']:
                        if video_url:
                            existing['video_url'] = video_url
                        found = True
                        break
                
                if not found:
                    # Add as new episode if not found (fallback)
                    episodes_list.append({
                        'title': clean_title,
                        'url': self.base_url or "",
                        'id': str(ch.get('id', hash(clean_title))),
                        'video_url': video_url
                    })

    def _parse_video_object(self, obj, episodes_list):
        """Helper to extract episode info from VideoObject"""
        title = obj.get('name', 'Unknown Episode')
        content_url = obj.get('contentUrl')
        page_url = obj.get('url') # The page URL
        
        # Even if content_url is missing (locked), we add it so it shows in the UI
        # Generate a consistent ID
        ep_id = f"{page_url}-{title}" 
        
        episodes_list.append({
            'title': title,
            'url': page_url,
            'id': str(hash(ep_id)),
            'video_url': content_url # Might be None
        })

    def extract_video_url(self, episode):
        """
        For GoodShort, we often get the video URL directly from the listing.
        If it was found during fetch_drama_info, return it.
        Otherwise, fetch the specific page (logic same as fetch_drama_info essentially).
        """
        if isinstance(episode, dict) and episode.get('video_url'):
            return self._normalize_video_url(episode['video_url'])

        episode_url = episode.get('url') if isinstance(episode, dict) else episode
        if not episode_url:
            return None

        headers = self.headers.copy()
        headers['Referer'] = episode_url
        response = self.session.get(episode_url, headers=headers)
        response.raise_for_status()
        html = response.text

        m3u8_matches = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        if m3u8_matches:
            return self._normalize_video_url(m3u8_matches[0])

        mp4_matches = re.findall(r'(https?://[^\s"\']+\.mp4[^\s"\']*)', html)
        if mp4_matches:
            return self._normalize_video_url(mp4_matches[0])

        next_data = self._extract_next_data(html)
        if next_data:
            candidate = self._find_first_value(next_data, {
                "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url", "videoSrc"
            })
            if candidate:
                return self._normalize_video_url(candidate)

        initial_state = self._extract_initial_state(html)
        if initial_state:
            candidate = self._find_first_value(initial_state, {
                "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url", "videoSrc"
            })
            if candidate:
                return self._normalize_video_url(candidate)

        return None

    def _extract_next_data(self, html):
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except Exception:
            return None

    def _extract_initial_state(self, html):
        match = re.search(r'window\.__INITIAL_STATE__=(.*?);?\s*(\n|<)', html)
        if not match:
            match = re.search(r'window\.__INITIAL_STATE__=(.*)', html)
        if not match:
            return None
        json_str = self._extract_balanced_json(html, match.start(1))
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except Exception:
            return None

    def _find_first_value(self, data, keys):
        if isinstance(data, dict):
            for k, v in data.items():
                if k in keys and isinstance(v, str) and v:
                    return v
                res = self._find_first_value(v, keys)
                if res:
                    return res
        elif isinstance(data, list):
            for item in data:
                res = self._find_first_value(item, keys)
                if res:
                    return res
        return None

    def _normalize_video_url(self, url):
        if not url:
            return None
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"https://www.goodshort.com{url}"
        return url

    def download_file(self, url, output_path, progress_callback=None, cancel_event=None, referer=None):
        """
        Downloads a file. Re-implemented here to be self-contained or we could inherit.
        """
        try:
            if ".m3u8" in url:
                self._download_m3u8(url, output_path, progress_callback, cancel_event, referer)
                return

            headers = self.headers.copy()
            if referer:
                headers['Referer'] = referer

            response = requests.get(url, stream=True, headers=headers)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if cancel_event and cancel_event.is_set():
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")

    def _download_m3u8(self, url, output_path, progress_callback, cancel_event, referer=None):
        import subprocess
        import threading
        import queue
        
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            ffmpeg_exe = "ffmpeg"
        
        ffmpeg_headers = {}
        if referer:
            ffmpeg_headers['Referer'] = referer
        
        # Add Cookie to ffmpeg headers if present in self.headers
        if 'Cookie' in self.headers:
            ffmpeg_headers['Cookie'] = self.headers['Cookie']
            
        headers_str = "".join([f"{k}: {v}\r\n" for k, v in ffmpeg_headers.items()])
        
        cmd = [
            ffmpeg_exe, "-y", 
            "-user_agent", self.headers['User-Agent'],
            "-headers", headers_str,
            "-i", url, 
            "-c", "copy", "-bsf:a", "aac_adtstoasc", 
            output_path
        ]
        
        # Use a queue to pass lines from the reader thread to the main thread
        log_queue = queue.Queue()
        
        def reader(pipe, q):
            try:
                for line in iter(pipe.readline, ''):
                    q.put(line)
                pipe.close()
            except:
                pass

        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                bufsize=1, 
                universal_newlines=True,
                encoding='utf-8', 
                errors='replace'
            )
        except FileNotFoundError:
             raise Exception(f"FFmpeg not found at '{ffmpeg_exe}'.")
        
        # Start reader thread
        t = threading.Thread(target=reader, args=(process.stderr, log_queue))
        t.daemon = True
        t.start()
        
        duration = 0
        last_progress_time = 0
        
        def parse_time(time_str):
            try:
                parts = time_str.split(':')
                h = int(parts[0])
                m = int(parts[1])
                s = float(parts[2])
                return h * 3600 + m * 60 + s
            except:
                return 0

        while True:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                return

            if process.poll() is not None:
                break
            
            while not log_queue.empty():
                try:
                    line = log_queue.get_nowait().strip()
                    
                    if "Duration:" in line:
                        match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                        if match:
                            duration = parse_time(match.group(1))
                    
                    if "time=" in line and progress_callback:
                        match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                        if match:
                            current_time = parse_time(match.group(1))
                            if duration > 0:
                                percent = (current_time / duration) * 100
                                if time.time() - last_progress_time > 0.5:
                                    progress_callback(int(percent), 100)
                                    last_progress_time = time.time()
                except queue.Empty:
                    break
            
            time.sleep(0.1)
        
        stderr_output = []
        while not log_queue.empty():
            stderr_output.append(log_queue.get())
        
        if process.returncode != 0:
            error_msg = "".join(stderr_output[-10:])
            raise Exception(f"FFmpeg download failed: {error_msg}")
        else:
            if progress_callback:
                progress_callback(100, 100)
