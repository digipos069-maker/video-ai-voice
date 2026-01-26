import requests
from bs4 import BeautifulSoup
import re
import os
import time
from urllib.parse import urlparse

class DramaboxDownloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.dramabox.com/'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def set_cookie(self, cookie_str):
        """Sets the Cookie header for requests."""
        if cookie_str:
            self.headers['Cookie'] = cookie_str
            self.session.headers.update({'Cookie': cookie_str})

    def _build_cookie_header(self):
        cookies = {}
        if self.session and self.session.cookies:
            cookies.update(self.session.cookies.get_dict())
        header_cookie = self.headers.get('Cookie')
        if header_cookie:
            for pair in header_cookie.split(';'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    cookies[k.strip()] = v.strip()
        if not cookies:
            return None
        return "; ".join([f"{k}={v}" for k, v in cookies.items()])

    def _origin_from_referer(self, referer):
        if not referer:
            return "https://www.dramabox.com"
        parsed = urlparse(referer)
        if not parsed.scheme or not parsed.netloc:
            return "https://www.dramabox.com"
        return f"{parsed.scheme}://{parsed.netloc}"

    def fetch_drama_info(self, url):
        """
        Fetches drama title and list of episodes from the given URL.
        Returns:
            dict: {
                'title': str,
                'episodes': [
                    {'title': str, 'url': str, 'id': str}
                ]
            }
        """
        try:
            headers = self.headers.copy()
            headers['Referer'] = url
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 1. Extract Title
            # Trying common meta tags or h1
            title = "Unknown Drama"
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "").split(" EP.")[0].strip()
            else:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)

            # 2. Extract Episodes
            # Heuristic: Look for links that look like episode links
            # The URL format: /ep/42000003486_kissing-the-wrong-brother/700215503_Episode-1
            # We look for links containing '/ep/' and the drama ID if possible.
            
            episodes = []
            
            # Extract base path for episodes to filter irrelevant links
            # url path: /ep/DRAMA_ID_SLUG/EPISODE_ID_SLUG
            # We want to match /ep/DRAMA_ID_SLUG/*
            
            # Simple heuristic: Find all 'a' tags, filter those that look like episodes
            links = soup.find_all('a', href=True)
            seen_urls = set()

            for link in links:
                href = link['href']
                if '/ep/' in href or '/video/' in href:
                    full_url = href if href.startswith('http') else 'https://www.dramabox.com' + href
                    
                    # Deduplicate
                    if full_url in seen_urls:
                        continue
                    
                    # Check if it looks like an episode (has 'Episode' or numbers)
                    text = link.get_text(strip=True)
                    if not text:
                        continue
                        
                    # Basic filtering
                    seen_urls.add(full_url)
                    episodes.append({
                        'title': text,
                        'url': full_url,
                        'id': full_url.split('/')[-1] # Simple ID
                    })

            # If we got nothing, fall back to single-episode page.
            if not episodes and "/video/" in url:
                episodes.append({
                    'title': title or "Episode",
                    'url': url,
                    'id': url.split('/')[-1]
                })

            # Sort episodes if possible (by number)
            # This is best effort
            def extract_ep_num(ep):
                # Try to find number in title
                match = re.search(r'(\d+)', ep['title'])
                if match:
                    return int(match.group(1))
                # Try URL
                match = re.search(r'Episode-(\d+)', ep['url'])
                if match:
                    return int(match.group(1))
                return 999999

            episodes.sort(key=extract_ep_num)

            return {
                'title': title,
                'episodes': episodes
            }

        except Exception as e:
            raise Exception(f"Failed to fetch drama info: {str(e)}")

    def extract_video_url(self, episode_url):
        """
        Attempts to find the actual video URL (mp4/m3u8) from the episode page.
        """
        try:
            if isinstance(episode_url, dict):
                episode_url = episode_url.get('url')
            if not episode_url:
                return None
            headers = self.headers.copy()
            headers['Referer'] = episode_url
            response = self.session.get(episode_url, headers=headers)
            response.raise_for_status()
            html = response.text
            
            # 1. Look for .m3u8
            m3u8_matches = re.findall(r'(https?://[^\s"\\]+\.m3u8[^\s"\\]*)', html)
            if m3u8_matches:
                return m3u8_matches[0]
                
            # 2. Look for .mp4
            mp4_matches = re.findall(r'(https?://[^\s"\\]+\.mp4[^\s"\\]*)', html)
            if mp4_matches:
                return mp4_matches[0]
            
            # 3. Look for generic video source patterns in JS
            # "url": "..." or "src": "..."
            # This is a very rough heuristic
            
            # If failed, return None
            return None

        except Exception as e:
            print(f"Error extracting video from {episode_url}: {e}")
            return None

    def download_file(self, url, output_path, progress_callback=None, cancel_event=None, referer=None):
        """
        Downloads a file from url to output_path.
        progress_callback: function(current_bytes, total_bytes)
        cancel_event: threading.Event to signal cancellation
        referer: str, optional specific referer URL (e.g. the episode page)
        """
        try:
            # Check if it's m3u8, if so, we might need ffmpeg (moviepy dependency)
            if ".m3u8" in url:
                self._download_m3u8(url, output_path, progress_callback, cancel_event, referer)
                return

            headers = self.headers.copy()
            if referer:
                headers['Referer'] = referer

            response = self.session.get(url, stream=True, headers=headers)
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
        """
        Wrapper to download m3u8 using ffmpeg with real-time progress parsing.
        """
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
            ffmpeg_headers['Origin'] = self._origin_from_referer(referer)
        ffmpeg_headers['User-Agent'] = self.headers['User-Agent']

        # Warm up CDN cookies (some endpoints set short-lived tokens per request)
        try:
            pre_headers = ffmpeg_headers.copy()
            pre_headers['Accept'] = "*/*"
            self.session.get(url, headers=pre_headers, timeout=15)
        except Exception:
            pass
        
        # Add Cookie to ffmpeg headers if present in self.headers
        cookie_header = self._build_cookie_header()
        if cookie_header:
            ffmpeg_headers['Cookie'] = cookie_header
            
        headers_str = "".join([f"{k}: {v}\r\n" for k, v in ffmpeg_headers.items()])
        
        cmd = [
            ffmpeg_exe, "-y",
            "-user_agent", self.headers['User-Agent'],
        ]
        if referer:
            cmd.extend(["-referer", referer])
        cmd.extend([
            "-headers", headers_str,
            "-i", url,
            "-c", "copy", "-bsf:a", "aac_adtstoasc",
            output_path
        ])
        
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
            # open subprocess with text mode
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
             raise Exception(f"FFmpeg not found at '{ffmpeg_exe}'. Please install ffmpeg or imageio-ffmpeg.")
        
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
            # Check cancellation
            if cancel_event and cancel_event.is_set():
                process.terminate()
                return

            # Check if process is done
            if process.poll() is not None:
                break
            
            # Consume all available lines
            while not log_queue.empty():
                try:
                    line = log_queue.get_nowait().strip()
                    
                    # 1. Parse Duration
                    if "Duration:" in line:
                        match = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                        if match:
                            duration = parse_time(match.group(1))
                    
                    # 2. Parse Progress
                    if "time=" in line and progress_callback:
                        match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                        if match:
                            current_time = parse_time(match.group(1))
                            if duration > 0:
                                percent = (current_time / duration) * 100
                                # Only emit if changed significantly or throttled
                                if time.time() - last_progress_time > 0.5:
                                    progress_callback(int(percent), 100) # Sending fake 'bytes' as percent/100
                                    last_progress_time = time.time()
                except queue.Empty:
                    break
            
            time.sleep(0.1)
        
        # Ensure we consume remaining logs if any error occurred
        stderr_output = []
        while not log_queue.empty():
            stderr_output.append(log_queue.get())
            
        if process.returncode != 0:
            error_msg = "".join(stderr_output[-10:]) # Last 10 lines
            raise Exception(f"FFmpeg download failed: {error_msg}")
        else:
            if progress_callback:
                progress_callback(100, 100) # Finish
