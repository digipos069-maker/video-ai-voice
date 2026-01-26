import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QProgressBar, QCheckBox, QFileDialog, 
                             QMessageBox, QGroupBox, QGridLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject

from core.dramabox_downloader import DramaboxDownloader
from core.goodshort_downloader import GoodShortDownloader
from core.settings_manager import SettingsManager

def get_downloader(url):
    if "goodshort.com" in url:
        return GoodShortDownloader()
    else:
        # Default to Dramabox for now or based on url
        return DramaboxDownloader()

class AnalysisWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, url, cookie=None):
        super().__init__()
        self.url = url
        self.cookie = cookie

    def run(self):
        try:
            downloader = get_downloader(self.url)
            if self.cookie:
                downloader.set_cookie(self.cookie)
            info = downloader.fetch_drama_info(self.url)
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))

class DownloadWorker(QThread):
    progress = pyqtSignal(str, int, int) # episode_id, current, total
    finished = pyqtSignal(str, bool, str) # episode_id, success, message
    
    def __init__(self, episode, output_folder, cookie=None):
        super().__init__()
        self.episode = episode
        self.output_folder = output_folder
        self.cookie = cookie
        self.is_cancelled = False
        # We need to know which downloader to use. 
        # Ideally, the episode dict should store the source type or we infer from URL again.
        # Since we have the episode URL, we can infer.
        self.downloader = get_downloader(episode['url'])
        if self.cookie:
            self.downloader.set_cookie(self.cookie)

    def run(self):
        try:
            # 1. Get Video URL
            # Some downloaders (GoodShort) might have it pre-filled in 'video_url' key
            video_url = self.downloader.extract_video_url(self.episode)
            
            # If not returned by extract_video_url (Dramabox style), try generic extraction if implemented there
            # But the interface for extract_video_url in Dramabox takes a URL string, 
            # while GoodShort takes the episode dict (modified in previous step).
            # Let's standardize: pass the whole episode dict or just the url if that's what it wants.
            
            if not video_url:
                 # Fallback for Dramabox legacy signature
                 if hasattr(self.downloader, 'extract_video_url'):
                     # Check signature or try/except
                     try:
                        video_url = self.downloader.extract_video_url(self.episode['url'])
                     except:
                        pass

            if not video_url:
                self.finished.emit(self.episode['id'], False, "Could not find video URL (Locked?)")
                return

            # 2. Download
            filename = f"{self.episode['title']}.mp4".replace(":", "").replace("?", "").replace("/", "_")
            filepath = os.path.join(self.output_folder, filename)
            
            def progress_callback(current, total):
                self.progress.emit(self.episode['id'], current, total)

            self.downloader.download_file(video_url, filepath, progress_callback, referer=self.episode['url'])
            
            self.finished.emit(self.episode['id'], True, "Completed")
            
        except Exception as e:
            self.finished.emit(self.episode['id'], False, str(e))

    def cancel(self):
        self.is_cancelled = True

class DownloaderTab(QWidget):
    def __init__(self):
        super().__init__()
        # self.downloader = DramaboxDownloader() # Removed, dynamic now
        self.episodes = [] # List of dicts
        self.active_downloads = {} # episode_id -> worker
        self.download_queue = [] # List of episode dicts
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Top: Input ---
        input_group = QGroupBox("Target Drama")
        input_layout = QGridLayout()
        
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("Paste URL here (Dramabox or GoodShort)")
        input_layout.addWidget(QLabel("URL:"), 0, 0)
        input_layout.addWidget(self.txt_url, 0, 1)
        
        self.btn_analyze = QPushButton("Fetch Episodes")
        self.btn_analyze.clicked.connect(self.start_analysis)
        input_layout.addWidget(self.btn_analyze, 0, 2)

        # Cookie Input
        self.txt_cookie = QLineEdit()
        self.txt_cookie.setPlaceholderText("Paste 'Cookie' string or load from file...")
        self.btn_load_cookie = QPushButton("Load Cookie File")
        self.btn_load_cookie.clicked.connect(self.browse_cookie_file)
        
        input_layout.addWidget(QLabel("Cookie:"), 1, 0)
        input_layout.addWidget(self.txt_cookie, 1, 1)
        input_layout.addWidget(self.btn_load_cookie, 1, 2)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # --- Middle: List ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["", "Episode Title", "Status", "Progress"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # Checkbox
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)          # Title
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents) # Status
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents) # Progress
        self.table.setColumnWidth(3, 200)
        layout.addWidget(self.table)

        # --- Bottom: Controls ---
        controls_layout = QHBoxLayout()
        
        # Select All
        self.chk_select_all = QCheckBox("Select All")
        self.chk_select_all.stateChanged.connect(self.toggle_select_all)
        controls_layout.addWidget(self.chk_select_all)
        
        controls_layout.addStretch()
        
        # Output Folder
        controls_layout.addWidget(QLabel("Save to:"))
        self.txt_out_dir = QLineEdit()
        self.txt_out_dir.setReadOnly(True)
        default_dir = os.path.join(os.getcwd(), "downloads")
        if not os.path.exists(default_dir):
            os.makedirs(default_dir)
        self.txt_out_dir.setText(SettingsManager.get_setting("download_folder", default_dir))
        controls_layout.addWidget(self.txt_out_dir)
        
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.clicked.connect(self.browse_folder)
        controls_layout.addWidget(self.btn_browse)
        
        # Download Button
        self.btn_download = QPushButton("Download Selected")
        self.btn_download.clicked.connect(self.start_download_batch)
        controls_layout.addWidget(self.btn_download)
        
        layout.addLayout(controls_layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.txt_out_dir.text())
        if folder:
            self.txt_out_dir.setText(folder)
            SettingsManager.save_setting("download_folder", folder)

    def browse_cookie_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Cookie File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Simple heuristic to detect Netscape format
                if "# Netscape HTTP Cookie File" in content or "\t" in content:
                    parsed_cookies = []
                    for line in content.splitlines():
                        if line.startswith('#') or not line.strip():
                            continue
                        parts = line.strip().split('\t')
                        if len(parts) >= 7:
                            # domain flag path secure expiration name value
                            name = parts[5]
                            value = parts[6]
                            parsed_cookies.append(f"{name}={value}")
                    
                    cookie_str = "; ".join(parsed_cookies)
                else:
                    # Assume raw string or JSON (if JSON, user needs to ensure it's simple key-value?)
                    # For now, treat as raw string if it looks like one, or try to clean it up
                    cookie_str = content.strip()
                
                self.txt_cookie.setText(cookie_str)
                QMessageBox.information(self, "Success", "Cookies loaded successfully!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load cookie file:\n{e}")

    def start_analysis(self):
        url = self.txt_url.text().strip()
        cookie = self.txt_cookie.text().strip()
        if not url:
            return
            
        self.btn_analyze.setEnabled(False)
        self.table.setRowCount(0)
        self.episodes = []
        
        self.worker_analysis = AnalysisWorker(url, cookie if cookie else None)
        self.worker_analysis.finished.connect(self.on_analysis_finished)
        self.worker_analysis.error.connect(self.on_analysis_error)
        self.worker_analysis.start()

    def on_analysis_finished(self, info):
        self.btn_analyze.setEnabled(True)
        self.episodes = info['episodes']
        
        self.table.setRowCount(len(self.episodes))
        for i, ep in enumerate(self.episodes):
            # Col 0: Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, chk_item)
            
            # Col 1: Title
            self.table.setItem(i, 1, QTableWidgetItem(ep['title']))
            
            # Col 2: Status
            self.table.setItem(i, 2, QTableWidgetItem("Pending"))
            
            # Col 3: Progress Bar
            pbar = QProgressBar()
            pbar.setValue(0)
            pbar.setTextVisible(False)
            self.table.setCellWidget(i, 3, pbar)
            
            # Store row index in episode dict for easy lookup
            ep['row_index'] = i

    def on_analysis_error(self, err):
        self.btn_analyze.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to fetch episodes:\n{err}")

    def toggle_select_all(self, state):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            item.setCheckState(state)

    def start_download_batch(self):
        selected_episodes = []
        for i, ep in enumerate(self.episodes):
            item = self.table.item(i, 0)
            if item.checkState() == Qt.Checked:
                status_item = self.table.item(i, 2)
                if status_item.text() not in ["Completed", "Downloading"]:
                    selected_episodes.append(ep)
        
        if not selected_episodes:
            QMessageBox.warning(self, "Warning", "No new episodes selected.")
            return

        self.download_queue.extend(selected_episodes)
        self.process_queue()

    def process_queue(self):
        # Limit concurrent downloads to 1 for stability, or 2
        MAX_CONCURRENT = 1
        
        while len(self.active_downloads) < MAX_CONCURRENT and self.download_queue:
            ep = self.download_queue.pop(0)
            self.start_single_download(ep)

    def start_single_download(self, ep):
        cookie = self.txt_cookie.text().strip()
        worker = DownloadWorker(ep, self.txt_out_dir.text(), cookie if cookie else None)
        worker.progress.connect(self.update_progress)
        worker.finished.connect(self.on_download_finished)
        
        self.active_downloads[ep['id']] = worker
        
        # Update UI
        row = ep['row_index']
        self.table.item(row, 2).setText("Downloading")
        self.table.cellWidget(row, 3).setValue(0)
        self.table.cellWidget(row, 3).setTextVisible(True)
        
        worker.start()

    def update_progress(self, ep_id, current, total):
        # Find episode by ID (a bit inefficient but safe)
        ep = next((e for e in self.episodes if e['id'] == ep_id), None)
        if ep:
            row = ep['row_index']
            pbar = self.table.cellWidget(row, 3)
            if total > 0:
                percent = int((current / total) * 100)
                pbar.setValue(percent)
            else:
                pbar.setRange(0, 0) # Indeterminate

    def on_download_finished(self, ep_id, success, message):
        if ep_id in self.active_downloads:
            del self.active_downloads[ep_id]
            
        ep = next((e for e in self.episodes if e['id'] == ep_id), None)
        if ep:
            row = ep['row_index']
            self.table.item(row, 2).setText(message)
            pbar = self.table.cellWidget(row, 3)
            if success:
                pbar.setValue(100)
                pbar.setStyleSheet("QProgressBar::chunk { background-color: #2ECC71; }")
            else:
                pbar.setValue(0)
                pbar.setStyleSheet("QProgressBar::chunk { background-color: #E74C3C; }")
        
        # Continue queue
        self.process_queue()