"""
網頁版 RSS Podcast 下載器
使用 Flask 提供 Web 圖形介面
"""

import os
import json
import threading
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file

from rss_downloader.parser import parse_rss
from rss_downloader.downloader import download_episode, DownloadError

app = Flask(__name__)

# 全域狀態
download_status = {
    "is_downloading": False,
    "current": 0,
    "total": 0,
    "current_file": "",
    "completed_files": []
}

# 預設下載目錄
DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "Podcasts")

# HTML 模板
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RSS Podcast 下載器</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
            font-size: 28px;
        }
        
        h1 span {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        input[type="text"] {
            flex: 1;
            padding: 15px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input[type="text"]:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        
        .podcast-info {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            display: none;
        }
        
        .podcast-info.visible {
            display: block;
        }
        
        .podcast-title {
            font-size: 20px;
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
        }
        
        .podcast-count {
            color: #666;
        }
        
        .controls {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .controls label {
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
        }
        
        .range-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .range-controls input {
            width: 60px;
            padding: 8px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            text-align: center;
        }
        
        .episode-list {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .episode-item {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            border-bottom: 1px solid #f0f0f0;
            transition: background 0.2s;
        }
        
        .episode-item:hover {
            background: #f8f9fa;
        }
        
        .episode-item:last-child {
            border-bottom: none;
        }
        
        .episode-item input[type="checkbox"] {
            width: 18px;
            height: 18px;
            margin-right: 12px;
            cursor: pointer;
        }
        
        .episode-index {
            font-family: monospace;
            color: #888;
            min-width: 60px;
        }
        
        .episode-title {
            flex: 1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .episode-date {
            color: #888;
            font-size: 14px;
            margin-left: 10px;
        }
        
        .download-section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .download-dir {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .progress-container {
            display: none;
        }
        
        .progress-container.visible {
            display: block;
        }
        
        .progress-bar {
            width: 100%;
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 10px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
        }
        
        .progress-text {
            text-align: center;
            color: #666;
        }
        
        .selected-count {
            background: #667eea;
            color: white;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 14px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .toast {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #333;
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s;
        }
        
        .toast.show {
            opacity: 1;
            transform: translateY(0);
        }
        
        .toast.success {
            background: #28a745;
        }
        
        .toast.error {
            background: #dc3545;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📻 <span>RSS Podcast 下載器</span></h1>
        
        <div class="input-group">
            <input type="text" id="rssUrl" placeholder="請輸入 RSS 連結..." 
                   value="https://feed.firstory.me/rss/user/clcftm46z000201z45w1c47fi">
            <button class="btn-primary" id="loadBtn" onclick="loadRSS()">載入</button>
        </div>
        
        <div class="podcast-info" id="podcastInfo">
            <div class="podcast-title" id="podcastTitle"></div>
            <div class="podcast-count" id="podcastCount"></div>
        </div>
        
        <div id="episodesSection" style="display: none;">
            <div class="controls">
                <label>
                    <input type="checkbox" id="selectAll" onchange="toggleSelectAll()">
                    全選
                </label>
                <div class="range-controls">
                    <span>從第</span>
                    <input type="number" id="fromEp" value="1" min="1">
                    <span>集到第</span>
                    <input type="number" id="toEp" value="10" min="1">
                    <span>集</span>
                    <button class="btn-secondary" onclick="applyRange()">套用</button>
                </div>
                <span class="selected-count" id="selectedCount">已選: 0 集</span>
            </div>
            
            <div class="episode-list" id="episodeList"></div>
            
            <div class="download-section">
                <div class="download-dir">
                    <input type="text" id="downloadDir" value="{{ download_dir }}" style="flex: 1;">
                </div>
                
                <div class="progress-container" id="progressContainer">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                    </div>
                    <div class="progress-text" id="progressText">準備中...</div>
                </div>
                
                <button class="btn-primary" id="downloadBtn" onclick="startDownload()" style="width: 100%; margin-top: 15px;">
                    🚀 開始下載
                </button>
            </div>
        </div>
        
        <div class="loading" id="loadingIndicator" style="display: none;">
            <div class="spinner"></div>
            <div>載入中...</div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        let episodes = [];
        
        function showToast(message, type = 'info') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + type;
            setTimeout(() => toast.className = 'toast', 3000);
        }
        
        async function loadRSS() {
            const url = document.getElementById('rssUrl').value.trim();
            if (!url) {
                showToast('請輸入 RSS 連結', 'error');
                return;
            }
            
            document.getElementById('loadBtn').disabled = true;
            document.getElementById('loadingIndicator').style.display = 'block';
            document.getElementById('episodesSection').style.display = 'none';
            
            try {
                const response = await fetch('/api/parse', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showToast(data.error, 'error');
                    return;
                }
                
                episodes = data.episodes;
                
                // 顯示 Podcast 資訊
                document.getElementById('podcastInfo').classList.add('visible');
                document.getElementById('podcastTitle').textContent = data.title;
                document.getElementById('podcastCount').textContent = `共 ${episodes.length} 集`;
                
                // 更新範圍
                document.getElementById('toEp').value = Math.min(10, episodes.length);
                document.getElementById('toEp').max = episodes.length;
                document.getElementById('fromEp').max = episodes.length;
                
                // 渲染列表
                renderEpisodeList();
                document.getElementById('episodesSection').style.display = 'block';
                
                showToast('載入成功！', 'success');
                
            } catch (error) {
                showToast('載入失敗: ' + error.message, 'error');
            } finally {
                document.getElementById('loadBtn').disabled = false;
                document.getElementById('loadingIndicator').style.display = 'none';
            }
        }
        
        function renderEpisodeList() {
            const list = document.getElementById('episodeList');
            list.innerHTML = episodes.map((ep, i) => `
                <div class="episode-item">
                    <input type="checkbox" id="ep_${i}" onchange="updateSelectedCount()">
                    <span class="episode-index">EP${String(ep.index).padStart(3, '0')}</span>
                    <span class="episode-title" title="${ep.title}">${ep.title}</span>
                    <span class="episode-date">${ep.published}</span>
                </div>
            `).join('');
            updateSelectedCount();
        }
        
        function toggleSelectAll() {
            const checked = document.getElementById('selectAll').checked;
            episodes.forEach((_, i) => {
                document.getElementById(`ep_${i}`).checked = checked;
            });
            updateSelectedCount();
        }
        
        function applyRange() {
            const from = parseInt(document.getElementById('fromEp').value) || 1;
            const to = parseInt(document.getElementById('toEp').value) || episodes.length;
            
            episodes.forEach((ep, i) => {
                const checkbox = document.getElementById(`ep_${i}`);
                checkbox.checked = ep.index >= from && ep.index <= to;
            });
            
            document.getElementById('selectAll').checked = false;
            updateSelectedCount();
        }
        
        function updateSelectedCount() {
            const count = episodes.filter((_, i) => document.getElementById(`ep_${i}`).checked).length;
            document.getElementById('selectedCount').textContent = `已選: ${count} 集`;
        }
        
        function getSelectedEpisodes() {
            return episodes.filter((_, i) => document.getElementById(`ep_${i}`).checked);
        }
        
        async function startDownload() {
            const selected = getSelectedEpisodes();
            if (selected.length === 0) {
                showToast('請選擇至少一集', 'error');
                return;
            }
            
            const downloadDir = document.getElementById('downloadDir').value.trim();
            if (!downloadDir) {
                showToast('請輸入下載目錄', 'error');
                return;
            }
            
            // 開始下載，不需要確認對話框
            showToast(`開始下載 ${selected.length} 集...`, 'info');
            
            document.getElementById('downloadBtn').disabled = true;
            document.getElementById('progressContainer').classList.add('visible');
            
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            
            let completed = 0;
            
            for (const ep of selected) {
                progressText.textContent = `下載中 (${completed}/${selected.length}): ${ep.title.substring(0, 40)}...`;
                
                try {
                    const response = await fetch('/api/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            audio_url: ep.audio_url,
                            filename: ep.filename,
                            output_dir: downloadDir
                        })
                    });
                    
                    const result = await response.json();
                    if (result.error) {
                        console.error(`下載失敗: ${ep.title}`, result.error);
                    }
                } catch (error) {
                    console.error(`下載失敗: ${ep.title}`, error);
                }
                
                completed++;
                const percent = (completed / selected.length) * 100;
                progressFill.style.width = percent + '%';
            }
            
            progressText.textContent = `完成！成功下載 ${completed} 集`;
            document.getElementById('downloadBtn').disabled = false;
            showToast(`下載完成！共 ${completed} 集`, 'success');
        }
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """主頁面"""
    return render_template_string(HTML_TEMPLATE, download_dir=DEFAULT_DOWNLOAD_DIR)


@app.route('/api/parse', methods=['POST'])
def api_parse():
    """解析 RSS Feed"""
    try:
        data = request.json
        url = data.get('url', '')
        
        if not url:
            return jsonify({"error": "請提供 RSS URL"})
        
        info = parse_rss(url)
        
        episodes_data = []
        for ep in info.episodes:
            episodes_data.append({
                "index": ep.index,
                "title": ep.title,
                "published": ep.published.strftime("%Y-%m-%d"),
                "audio_url": ep.audio_url,
                "filename": ep.get_filename()
            })
        
        # 反轉順序，讓新的集數在最前面
        episodes_data.reverse()
        
        return jsonify({
            "title": info.title,
            "episodes": episodes_data
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/download', methods=['POST'])
def api_download():
    """下載單一音檔"""
    try:
        data = request.json
        audio_url = data.get('audio_url')
        filename = data.get('filename')
        output_dir = data.get('output_dir', DEFAULT_DOWNLOAD_DIR)
        
        # 確保目錄存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        filepath = Path(output_dir) / filename
        
        # 如果檔案已存在，跳過
        if filepath.exists() and filepath.stat().st_size > 0:
            return jsonify({"success": True, "path": str(filepath), "skipped": True})
        
        # 下載檔案
        import requests
        response = requests.get(audio_url, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return jsonify({"success": True, "path": str(filepath)})
        
    except Exception as e:
        return jsonify({"error": str(e)})


def run_server(port=8080):
    """啟動伺服器"""
    print(f"\n🚀 RSS Podcast 下載器已啟動！")
    print(f"📻 請在瀏覽器開啟: http://localhost:{port}")
    print(f"⌨️  按 Ctrl+C 停止伺服器\n")
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    run_server()
