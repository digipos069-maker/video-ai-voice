import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from urllib.parse import urlparse, urljoin, parse_qs, urlencode, urlunparse
import subprocess
import threading
import queue

class NetShortDownloader:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.netshort.com/'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.base_url = None

    def set_cookie(self, cookie_str):
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
            return "https://www.netshort.com"
        parsed = urlparse(referer)
        if not parsed.scheme or not parsed.netloc:
            return "https://www.netshort.com"
        return f"{parsed.scheme}://{parsed.netloc}"

    def _extract_balanced_json(self, text, start_index):
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

    def _find_all_strings(self, data, predicate):
        matches = set()
        def walk(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)
            elif isinstance(obj, str):
                if predicate(obj):
                    matches.add(obj)
        walk(data)
        return list(matches)

    def _normalize_video_url(self, url):
        if not url:
            return None
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"https://www.netshort.com{url}"
        return url

    def _unescape_js_url(self, value):
        if not value:
            return value
        value = value.replace("\\u002F", "/").replace("\\/", "/")
        value = value.replace("\\u003A", ":").replace("\\u0026", "&")
        return value

    def _guess_episode_title(self, href, fallback_index):
        match = re.search(r'ep(?:isode)?[-_ ]?(\d+)', href, re.IGNORECASE)
        if match:
            return f"EP {int(match.group(1))}"
        return f"Episode {fallback_index}"

    def _looks_like_episode(self, obj):
        if not isinstance(obj, dict):
            return False
        keys = {k.lower() for k in obj.keys()}
        episode_keys = {
            "episodeid", "episodename", "episodetitle", "episodenum", "episodeno",
            "chapterid", "chaptername", "chaptertitle", "chapternum", "chapterno",
            "epnum", "epno"
        }
        media_keys = {
            "m3u8path", "m3u8", "hlsurl", "playurl", "videourl", "mp4url",
            "videosrc", "resourceurl", "streamurl"
        }
        if keys.intersection(episode_keys):
            return True
        if keys.intersection(media_keys) and any("episode" in k or "chapter" in k for k in keys):
            return True
        return False

    def _extract_episode_candidates(self, data):
        candidates = []

        def walk(obj):
            if isinstance(obj, dict):
                if self._looks_like_episode(obj):
                    candidates.append(obj)
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        return candidates

    def _episode_from_candidate(self, obj, fallback_index):
        title = (
            obj.get("episodeName") or obj.get("episodeTitle") or obj.get("chapterName") or
            obj.get("chapterTitle") or obj.get("title") or obj.get("name")
        )
        if not title:
            title = f"Episode {fallback_index}"

        ep_num = 999999
        for k in ("episodeNum", "episodeNo", "chapterNum", "chapterNo", "epNum", "epNo", "sort", "serialNumber"):
            if k in obj:
                try:
                    ep_num = int(obj.get(k))
                    break
                except Exception:
                    pass
        if ep_num == 999999:
            match = re.search(r'(?:EP|Episode)\s?(\d+)', str(title), re.IGNORECASE)
            if match:
                ep_num = int(match.group(1))

        video_url = self._find_first_value(obj, {
            "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url",
            "videoSrc", "resourceUrl", "streamUrl"
        })
        if video_url:
            video_url = self._normalize_video_url(self._unescape_js_url(video_url))

        url = (
            obj.get("shareUrl") or obj.get("pageUrl") or obj.get("episodeUrl") or
            obj.get("url") or obj.get("jumpUrl")
        )
        if url:
            url = self._normalize_video_url(self._unescape_js_url(url))
        if not url:
            url = self.base_url or "https://www.netshort.com/"

        ep_id = obj.get("episodeId") or obj.get("chapterId") or obj.get("id")
        if not ep_id:
            ep_id = f"{url}-{title}"

        return {
            "title": title,
            "url": url,
            "id": str(hash(str(ep_id))),
            "ep_num": ep_num,
            "video_url": video_url
        }

    def _extract_episode_id(self, html, url):
        match = re.search(r'"episodeId"\s*:\s*"?(\\d+)"?', html)
        if match:
            return match.group(1)
        match = re.search(r'/episode/([^/?#]+)', url)
        if match:
            slug = match.group(1)
            digits = re.findall(r'\d+', slug)
            if digits:
                return digits[-1]
        return None

    def _extract_api_endpoints(self, html):
        candidates = set()
        for match in re.findall(r'(https?://[^\s"\'<>]+/api/[^\s"\'<>]+)', html):
            candidates.add(match)
        for match in re.findall(r'"/api/[^"\']+"', html):
            candidates.add("https://www.netshort.com" + match.strip('"'))
        filtered = [
            c for c in candidates
            if any(k in c.lower() for k in ("episode", "play", "video", "stream", "chapter"))
        ]
        return list(filtered)[:6]

    def _extract_api_endpoints_from_state(self, state):
        if not state:
            return []
        endpoints = self._find_all_strings(
            state,
            lambda v: "/api/" in v and ("netshort" in v or v.startswith("/"))
        )
        normalized = []
        for item in endpoints:
            if item.startswith("/"):
                normalized.append("https://www.netshort.com" + item)
            else:
                normalized.append(item)
        filtered = [
            c for c in normalized
            if any(k in c.lower() for k in ("episode", "play", "video", "stream", "chapter"))
        ]
        return filtered[:6]

    def _find_episode_object(self, data, episode_id):
        if not data or not episode_id:
            return None
        target = str(episode_id)

        def match_id(obj):
            for k in ("episodeId", "chapterId", "id", "episode_id", "chapter_id"):
                if k in obj and str(obj.get(k)) == target:
                    return True
            return False

        def walk(obj):
            if isinstance(obj, dict):
                if match_id(obj):
                    return obj
                for v in obj.values():
                    res = walk(v)
                    if res:
                        return res
            elif isinstance(obj, list):
                for item in obj:
                    res = walk(item)
                    if res:
                        return res
            return None

        return walk(data)

    def _append_query(self, url, params):
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for k, v in params.items():
            if k not in qs:
                qs[k] = [str(v)]
        new_query = urlencode(qs, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    def _probe_api_for_video(self, api_url, episode_id, referer):
        headers = self.headers.copy()
        headers['Referer'] = referer
        headers['Origin'] = self._origin_from_referer(referer)
        headers['X-Requested-With'] = 'XMLHttpRequest'
        param_names = ["episodeId", "episode_id", "epId", "chapterId", "id"]
        urls = []
        for name in param_names:
            urls.append(self._append_query(api_url, {name: episode_id}))

        payloads = [
            {"episodeId": episode_id},
            {"episode_id": episode_id},
            {"epId": episode_id},
            {"chapterId": episode_id},
            {"id": episode_id}
        ]

        def try_parse_response(resp):
            if resp.status_code != 200:
                return None
            text = resp.text
            m3u8_matches = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', text)
            if m3u8_matches:
                return self._normalize_video_url(m3u8_matches[0])
            mp4_matches = re.findall(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', text)
            if mp4_matches:
                return self._normalize_video_url(mp4_matches[0])
            try:
                data = resp.json()
            except Exception:
                data = None
            if data:
                candidate = self._find_first_value(data, {
                    "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url",
                    "videoSrc", "resourceUrl", "streamUrl"
                })
                if candidate:
                    candidate = self._unescape_js_url(candidate)
                    return self._normalize_video_url(candidate)
            return None

        for candidate_url in urls:
            try:
                resp = self.session.get(candidate_url, headers=headers, timeout=15)
                candidate = try_parse_response(resp)
                if candidate:
                    return candidate
            except Exception:
                continue

        for payload in payloads:
            try:
                resp = self.session.post(api_url, headers=headers, json=payload, timeout=15)
                candidate = try_parse_response(resp)
                if candidate:
                    return candidate
            except Exception:
                continue
        return None

    def fetch_drama_info(self, url):
        self.base_url = url
        all_episodes = {} # Keyed by URL to prevent duplicates
        
        # Clean URL to base for pagination
        # If url ends with /page/X, strip it
        base_url = re.sub(r'/page/\d+/?$', '', url)
        
        page = 1
        empty_pages_count = 0
        
        print(f"Starting fetch from: {base_url}")
        
        while True:
            # Construct page URL
            if page == 1:
                target_url = base_url
            else:
                target_url = f"{base_url}/page/{page}"
                
            print(f"Fetching page {page}: {target_url}")
            
            try:
                response = self.session.get(target_url, headers=self.headers)
                # NetShort might redirect to homepage or 404 if page invalid
                if response.status_code != 200 or response.url == "https://www.netshort.com/":
                    print(f"Page {page} invalid (Status {response.status_code} or Redirect). Stopping.")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract episodes from links
                found_on_page = 0
                links = soup.find_all('a', href=True)
                
                for a in links:
                    href = a['href']
                    if "/episode/" in href:
                        full_url = urljoin("https://www.netshort.com", href)
                        text = a.get_text(strip=True)

                        if not text or text.lower() == "play now":
                            text = self._guess_episode_title(href, len(all_episodes) + 1)
                            
                        # Check if it looks like an episode title "EP X-Title"
                        # But sometimes it's just the title
                        
                        # We use URL as unique ID
                        if full_url not in all_episodes:
                            # Try to parse EP number for sorting
                            ep_num = 999999
                            match = re.search(r'EP\s?(\d+)', text, re.IGNORECASE)
                            if match:
                                ep_num = int(match.group(1))
                            else:
                                # Try from URL
                                match_url = re.search(r'-ep-(\d+)', href, re.IGNORECASE)
                                if match_url:
                                    ep_num = int(match_url.group(1))
                                elif href.endswith("-2012451695560892417"): # First episode usually has ID only
                                     ep_num = 1
                            
                            all_episodes[full_url] = {
                                'title': text,
                                'url': full_url,
                                'id': str(hash(full_url)),
                                'ep_num': ep_num,
                                'video_url': None # Will extract later
                            }
                            found_on_page += 1

                # Extract episodes from embedded app state (often includes locked entries)
                state_candidates = []
                next_data = self._extract_next_data(response.text)
                if next_data:
                    state_candidates.extend(self._extract_episode_candidates(next_data))
                initial_state = self._extract_initial_state(response.text)
                if initial_state:
                    state_candidates.extend(self._extract_episode_candidates(initial_state))

                for idx, obj in enumerate(state_candidates, start=1):
                    ep = self._episode_from_candidate(obj, len(all_episodes) + idx)
                    key = ep.get("url") or ep.get("title")
                    if key in (self.base_url, "https://www.netshort.com/"):
                        key = ep.get("id") or ep.get("title")
                    if key not in all_episodes:
                        all_episodes[key] = ep
                        found_on_page += 1
                    else:
                        existing = all_episodes[key]
                        if not existing.get("video_url") and ep.get("video_url"):
                            existing["video_url"] = ep["video_url"]
                
                print(f"Found {found_on_page} new episodes on page {page}")
                
                if found_on_page == 0:
                    empty_pages_count += 1
                    if empty_pages_count >= 1: # Stop after 1 empty page (or maybe 2 to be safe?)
                        break
                else:
                    empty_pages_count = 0
                
                page += 1
                time.sleep(1) # Be nice
                
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break
        
        # Convert to list and sort
        episodes_list = list(all_episodes.values())
        episodes_list.sort(key=lambda x: x['ep_num'])
        
        # Drama Title
        # Try to get from first page soup if possible, or just use first episode text
        drama_title = "Unknown Drama"
        if episodes_list:
            # "EP 1-Title" -> "Title"
            first = episodes_list[0]['title']
            if "-" in first:
                parts = first.split("-", 1)
                if "EP" in parts[0]:
                    drama_title = parts[1].strip()
                else:
                    drama_title = first
            else:
                drama_title = first
                
        return {
            'title': drama_title,
            'episodes': episodes_list
        }

    def extract_video_url(self, episode):
        """
        Visits the episode page and tries to find the video URL.
        """
        if isinstance(episode, dict) and episode.get('video_url'):
            return self._normalize_video_url(episode['video_url'])

        url = episode['url'] if isinstance(episode, dict) else episode
        if not url:
            return None
        print(f"Extracting video for: {url}")
        
        try:
            headers = self.headers.copy()
            headers['Referer'] = url
            response = self.session.get(url, headers=headers)
            html = response.text
            
            # 1. Direct m3u8
            m3u8_matches = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m3u8_matches:
                return self._normalize_video_url(m3u8_matches[0])
                
            # 2. mp4
            mp4_matches = re.findall(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
            if mp4_matches:
                return self._normalize_video_url(mp4_matches[0])

            # 3. Parse embedded app state (Next.js / React state)
            next_data = self._extract_next_data(html)
            if next_data:
                episode_id = self._extract_episode_id(html, url)
                if episode_id:
                    episode_obj = self._find_episode_object(next_data, episode_id)
                    if episode_obj:
                        candidate = self._find_first_value(episode_obj, {
                            "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url",
                            "videoSrc", "resourceUrl", "streamUrl"
                        })
                        if candidate:
                            candidate = self._unescape_js_url(candidate)
                            return self._normalize_video_url(candidate)
                candidate = self._find_first_value(next_data, {
                    "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url",
                    "videoSrc", "resourceUrl", "streamUrl"
                })
                if candidate:
                    candidate = self._unescape_js_url(candidate)
                    return self._normalize_video_url(candidate)

            initial_state = self._extract_initial_state(html)
            if initial_state:
                episode_id = self._extract_episode_id(html, url)
                if episode_id:
                    episode_obj = self._find_episode_object(initial_state, episode_id)
                    if episode_obj:
                        candidate = self._find_first_value(episode_obj, {
                            "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url",
                            "videoSrc", "resourceUrl", "streamUrl"
                        })
                        if candidate:
                            candidate = self._unescape_js_url(candidate)
                            return self._normalize_video_url(candidate)
                candidate = self._find_first_value(initial_state, {
                    "m3u8Path", "m3u8", "hlsUrl", "playUrl", "videoUrl", "mp4Url",
                    "videoSrc", "resourceUrl", "streamUrl"
                })
                if candidate:
                    candidate = self._unescape_js_url(candidate)
                    return self._normalize_video_url(candidate)

            # 4. Try to extract URLs from JS literals (escaped JSON strings)
            js_match = re.search(
                r'"(m3u8Path|m3u8|hlsUrl|playUrl|videoUrl|mp4Url|videoSrc|resourceUrl|streamUrl)"\s*:\s*"(.*?)"',
                html
            )
            if js_match:
                candidate = self._unescape_js_url(js_match.group(2))
                if candidate:
                    return self._normalize_video_url(candidate)

            # 5. Probe embedded API endpoints with episodeId if present
            episode_id = self._extract_episode_id(html, url)
            if episode_id:
                api_urls = self._extract_api_endpoints(html)
                api_urls += self._extract_api_endpoints_from_state(next_data)
                api_urls += self._extract_api_endpoints_from_state(initial_state)
                deduped = []
                seen = set()
                for api_url in api_urls:
                    if api_url not in seen:
                        deduped.append(api_url)
                        seen.add(api_url)
                for api_url in deduped:
                    candidate = self._probe_api_for_video(api_url, episode_id, url)
                    if candidate:
                        return candidate
            
            # 6. Check for locked status or other indicators
            if "Authentication failed" in html or "Unlock" in html:
                return None

            return None
            
        except Exception as e:
            print(f"Extraction failed: {e}")
            return None

    def download_file(self, url, output_path, progress_callback=None, cancel_event=None, referer=None):
        try:
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
        ffmpeg_headers = {k: v for k, v in ffmpeg_headers.items() if v}
        
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
        
        if process.returncode != 0:
             # Just a warning as ffmpeg sometimes returns non-zero for minor warnings
             pass
        else:
            if progress_callback:
                progress_callback(100, 100)
