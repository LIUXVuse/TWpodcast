"""
🎙️ Podcast Pipeline Dashboard v5
- 修復刪除閃退
- 新增全選/載入更多功能
- 新增排程設定
"""

import os
import json
import shutil
import threading
import time
import yaml
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent))
from podcast_pipeline import PodcastPipeline
from podcast_pipeline.telegram_notifier import TelegramNotifier
from podcast_pipeline.git_publisher import GitPublisher
from rss_downloader.parser import parse_rss

app = Flask(__name__)
pipeline = None
CONFIG_DIR = Path(__file__).parent / 'config'
DATA_DIR = Path(__file__).parent / 'data'

# 監控狀態
watcher_status = {'running': False, 'logs': [], 'processed_count': 0, 'last_check': None}

# 排程設定
schedule_config = {'enabled': False, 'time': '20:00', 'max_episodes': 5}

# 排除前綴
EXCLUDE_PREFIXES = ['S3EP']

def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = PodcastPipeline()
    return pipeline

def load_feeds():
    feeds_file = CONFIG_DIR / 'feeds.yaml'
    if feeds_file.exists():
        with open(feeds_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return data.get('feeds', [])
    return []

def save_feeds(feeds):
    feeds_file = CONFIG_DIR / 'feeds.yaml'
    data = {'feeds': feeds, 'download': {'default_path': '~/Downloads/Podcasts', 'auto_cleanup': False, 'keep_recent': 10}}
    with open(feeds_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

def load_episode_metadata():
    meta_file = DATA_DIR / 'episode_metadata.json'
    if meta_file.exists():
        with open(meta_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_episode_metadata(metadata):
    meta_file = DATA_DIR / 'episode_metadata.json'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

def load_schedule_config():
    config_file = DATA_DIR / 'schedule_config.json'
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'enabled': False, 'time': '20:00', 'max_episodes': 5}

def save_schedule_config(config):
    config_file = DATA_DIR / 'schedule_config.json'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_telegram_config():
    """從 services.yaml 讀取 Telegram 設定"""
    services_file = CONFIG_DIR / 'services.yaml'
    if services_file.exists():
        with open(services_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return data.get('telegram', {})
    return {'enabled': False}

# ===== Telegram 廣播追蹤 =====
telegram_broadcast_enabled = True  # 廣播開關（runtime）

def load_broadcasted():
    """載入已廣播的摘要列表"""
    broadcast_file = DATA_DIR / 'broadcasted.json'
    if broadcast_file.exists():
        with open(broadcast_file, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_broadcasted(broadcasted: set):
    """儲存已廣播的摘要列表"""
    broadcast_file = DATA_DIR / 'broadcasted.json'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(broadcast_file, 'w', encoding='utf-8') as f:
        json.dump(list(broadcasted), f, ensure_ascii=False)

def mark_as_broadcasted(summary_name: str):
    """標記摘要為已廣播"""
    broadcasted = load_broadcasted()
    broadcasted.add(summary_name)
    save_broadcasted(broadcasted)

def is_broadcasted(summary_name: str) -> bool:
    """檢查摘要是否已廣播過"""
    return summary_name in load_broadcasted()

# ===== SMB 待傳佇列管理 =====
def load_pending_uploads():
    """載入待傳到 Whisper 的檔案列表"""
    pending_file = DATA_DIR / 'pending_uploads.json'
    if pending_file.exists():
        with open(pending_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_pending_uploads(pending: list):
    """儲存待傳檔案列表"""
    pending_file = DATA_DIR / 'pending_uploads.json'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(pending_file, 'w', encoding='utf-8') as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

def add_to_pending(filepath: str, target_filename: str):
    """將檔案加入待傳佇列"""
    pending = load_pending_uploads()
    item = {'filepath': filepath, 'target': target_filename}
    if item not in pending:
        pending.append(item)
        save_pending_uploads(pending)

def remove_from_pending(filepath: str):
    """從待傳佇列移除"""
    pending = load_pending_uploads()
    pending = [p for p in pending if p['filepath'] != filepath]
    save_pending_uploads(pending)

def process_pending_uploads():
    """處理待傳佇列：SMB 連線後自動補傳"""
    pending = load_pending_uploads()
    if not pending:
        return
    
    p = get_pipeline()
    if not p.whisper.is_connected():
        return  # SMB 還沒連上，等下次
    
    add_scheduler_log(f"🔄 發現 {len(pending)} 個待傳檔案，開始補傳...")
    
    success_count = 0
    for item in pending[:]:  # 用切片避免迭代時修改
        filepath = Path(item['filepath'])
        target = item['target']
        
        if not filepath.exists():
            remove_from_pending(str(filepath))
            continue
        
        try:
            p.whisper.submit_audio(filepath, target)
            remove_from_pending(str(filepath))
            add_scheduler_log(f"   ✅ 補傳成功：{target}", 'success')
            success_count += 1
        except Exception as e:
            add_scheduler_log(f"   ❌ 補傳失敗：{target} - {str(e)}", 'error')
    
    if success_count > 0:
        add_scheduler_log(f"📤 補傳完成：{success_count} 個檔案", 'success')

def add_log(msg, level='info'):
    watcher_status['logs'].append({'time': datetime.now().strftime('%H:%M:%S'), 'msg': msg, 'level': level})
    if len(watcher_status['logs']) > 100:
        watcher_status['logs'] = watcher_status['logs'][-100:]

def watcher_thread():
    p = get_pipeline()
    processed = set()
    
    # 載入 metadata 來正確追蹤已處理的逐字稿
    metadata = load_episode_metadata()
    existing_summaries = list(p.summaries_dir.glob('*_summary.md'))
    
    for f in existing_summaries:
        summary_name = f.stem.replace('_summary', '')
        # 從 metadata 反查對應的逐字稿 stem
        for stem, meta in metadata.items():
            feed_name = meta.get('feed_name', '')
            ep_index = meta.get('index', '')
            if feed_name and isinstance(ep_index, int):
                expected_name = f'{feed_name}EP{ep_index:03d}'
                if summary_name == expected_name:
                    processed.add(stem)  # 加入逐字稿的 stem
                    break
        else:
            # 舊格式或無 metadata 的情況
            processed.add(summary_name)
    
    add_log(f'🚀 監控已啟動，已有 {len(processed)} 個摘要')
    
    while watcher_status['running']:
        try:
            watcher_status['last_check'] = datetime.now().strftime('%H:%M:%S')
            # 每次掃描都重新載入 metadata 和 feeds（確保能讀取到最新設定）
            metadata = load_episode_metadata()
            feeds = load_feeds()
            transcripts = list(p.whisper.output_dir.glob('*_tw.txt'))
            
            for t in transcripts:
                if not watcher_status['running']:
                    break
                    
                stem = t.stem.replace('_tw', '')
                
                if any(stem.startswith(pf) for pf in EXCLUDE_PREFIXES):
                    continue
                
                if stem in processed:
                    continue
                
                add_log(f'🆕 發現新逐字稿：{t.name}')
                
                meta = metadata.get(stem, {})
                feed_name = meta.get('feed_name', '')
                ep_title = meta.get('title', '')
                ep_date = meta.get('published', '')
                ep_index = meta.get('index', None)
                
                # 智慧識別：如果沒有 metadata，嘗試從檔名 prefix 推斷
                if not feed_name:
                    # 嘗試解析檔名格式：PREFIX_EPXXX 或 EPXXX
                    import re
                    # 格式1: MM_EP301 → prefix=MM, index=301
                    match_prefix = re.match(r'^([A-Za-z]+)_EP(\d+)$', stem)
                    # 格式2: EP301 → prefix=None, index=301
                    match_ep = re.match(r'^EP(\d+)$', stem)
                    
                    if match_prefix:
                        prefix = match_prefix.group(1)
                        ep_index = int(match_prefix.group(2))
                        # 從 feeds 配置找對應的節目名稱
                        for feed in feeds:
                            if feed.get('prefix', '').upper() == prefix.upper():
                                feed_name = feed.get('name', '')
                                add_log(f'   🔍 從 prefix [{prefix}] 識別為：{feed_name}')
                                break
                    elif match_ep:
                        ep_index = int(match_ep.group(1))
                        add_log(f'   ⚠️ 無法識別節目（檔名只有 EP 編號），將使用原始檔名')
                
                # 計算預期的摘要檔名
                if feed_name and isinstance(ep_index, int):
                    summary_filename = f'{feed_name}EP{ep_index:03d}_summary.md'
                else:
                    summary_filename = f'{stem}_summary.md'
                
                # 檢查摘要是否已存在（避免重複處理）
                if (p.summaries_dir / summary_filename).exists():
                    add_log(f'   ⏭️ 摘要已存在，跳過：{summary_filename}')
                    processed.add(stem)
                    continue
                
                # 根據 feed_name 找到對應的模板
                template_id = 'stock_analysis'  # 預設
                for feed in feeds:
                    if feed.get('name') == feed_name:
                        template_id = feed.get('template', 'stock_analysis')
                        break
                
                # 組裝完整標題：節目名 EPXXX - 標題（日期）
                if feed_name:
                    full_title = f"{feed_name} EP{ep_index:03d}" if isinstance(ep_index, int) else f"{feed_name} {stem}"
                else:
                    full_title = stem
                if ep_title:
                    full_title += f" - {ep_title}"
                if ep_date:
                    full_title += f"（{ep_date}）"
                
                add_log(f'   📄 標題：{full_title[:60]}...')
                add_log(f'   🎨 使用模板：{template_id}')
                
                transcript = t.read_text(encoding='utf-8')
                result = p.summarizer.process(transcript, full_title, template_id)
                
                if result.success:
                    # 檔名格式：節目名EP集數_summary.md
                    if feed_name and isinstance(ep_index, int):
                        summary_filename = f'{feed_name}EP{ep_index:03d}_summary.md'
                    else:
                        summary_filename = f'{stem}_summary.md'
                    output = p.summaries_dir / summary_filename
                    output.write_text(result.summary, encoding='utf-8')
                    processed.add(stem)
                    watcher_status['processed_count'] += 1
                    add_log(f'   ✅ 已儲存：{summary_filename}', 'success')
                    
                    # 計算 summary_name（用於 Git 和 Telegram）
                    summary_name = summary_filename.replace('_summary.md', '')
                    
                    # 自動推送到 Git
                    try:
                        git_pub = GitPublisher()
                        if git_pub.enabled:
                            git_result = git_pub.publish(summary_name, output)
                            if git_result['success']:
                                add_log(f'   🚀 Git 已推送', 'success')
                                # 自動同步網站並再次推送
                                try:
                                    site_script = Path(__file__).parent / 'site' / 'scripts' / 'sync-content.js'
                                    if site_script.exists():
                                        import subprocess
                                        sync_result = subprocess.run(
                                            ['node', str(site_script)],
                                            cwd=Path(__file__).parent,
                                            capture_output=True,
                                            text=True,
                                            timeout=30
                                        )
                                        if sync_result.returncode == 0:
                                            add_log(f'   📦 網站目錄已同步', 'success')
                                            # 再次推送網站變更
                                            git_pub._run_git('add', 'site/')
                                            git_pub._run_git('commit', '-m', f'🌐 同步網站目錄：{summary_name}')
                                            push_ok, push_msg = git_pub._run_git('push')
                                            if push_ok:
                                                add_log(f'   🌐 網站已更新', 'success')
                                            else:
                                                add_log(f'   ⚠️ 網站推送失敗', 'warning')
                                        else:
                                            add_log(f'   ⚠️ 網站同步失敗', 'warning')
                                except Exception as se:
                                    add_log(f'   ⚠️ 網站同步錯誤：{str(se)}', 'warning')
                            else:
                                add_log(f'   ⚠️ Git 推送：{git_result["message"]}', 'warning')
                    except Exception as ge:
                        add_log(f'   ⚠️ Git 錯誤：{str(ge)}', 'warning')
                    
                    # 推送到 Telegram（檢查開關和是否已廣播）
                    try:
                        global telegram_broadcast_enabled
                        telegram_config = load_telegram_config()
                        
                        if not telegram_broadcast_enabled:
                            add_log(f'   📴 Telegram 廣播已關閉，跳過推送')
                            mark_as_broadcasted(summary_name)  # 仍標記為已處理
                        elif is_broadcasted(summary_name):
                            add_log(f'   ⏭️ 已廣播過，跳過')
                        elif telegram_config.get('enabled'):
                            notifier = TelegramNotifier(telegram_config)
                            tg_result = notifier.send_summary(output)
                            if tg_result.success:
                                mark_as_broadcasted(summary_name)
                                add_log(f'   📤 Telegram 推送成功', 'success')
                            else:
                                add_log(f'   ⚠️ Telegram 推送失敗：{tg_result.error}', 'warning')
                        else:
                            add_log(f'   📴 Telegram 未啟用')
                    except Exception as te:
                        add_log(f'   ⚠️ Telegram 錯誤：{str(te)}', 'warning')
                else:
                    add_log(f'   ❌ 失敗：{result.error}', 'error')
            
            time.sleep(30)
        except Exception as e:
            add_log(f'❌ 錯誤：{str(e)}', 'error')
            time.sleep(5)
    
    add_log('👋 監控已停止')

# ===== 排程掃描線程 =====
scheduler_status = {'running': False, 'last_run': None, 'logs': []}

def add_scheduler_log(msg, level='info'):
    scheduler_status['logs'].append({'time': datetime.now().strftime('%H:%M:%S'), 'msg': msg, 'level': level})
    if len(scheduler_status['logs']) > 50:
        scheduler_status['logs'] = scheduler_status['logs'][-50:]
    print(f"[排程] {msg}")

def scheduler_thread():
    """排程掃描線程 - 定時檢查 RSS 並下載最新集數"""
    import requests as req
    
    add_scheduler_log("📅 排程線程已啟動")
    checked_today = set()  # 記錄今天已檢查過的時間
    
    while True:
        try:
            config = load_schedule_config()
            
            if not config.get('enabled', False):
                time.sleep(60)  # 未啟用，每分鐘檢查一次
                continue
            
            now = datetime.now()
            current_time = now.strftime('%H:%M')
            current_date = now.strftime('%Y-%m-%d')
            
            # 重置每日記錄
            if scheduler_status.get('last_date') != current_date:
                checked_today.clear()
                scheduler_status['last_date'] = current_date
            
            # 取得設定的時間列表
            times = config.get('times', [config.get('time', '20:00')])
            max_episodes = config.get('max_episodes', 5)
            
            # 檢查是否到達掃描時間
            for scan_time in times:
                check_key = f"{current_date}_{scan_time}"
                if current_time == scan_time and check_key not in checked_today:
                    checked_today.add(check_key)
                    add_scheduler_log(f"⏰ 到達掃描時間 {scan_time}，開始掃描 RSS")
                    scheduler_status['last_run'] = now.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 執行掃描
                    try:
                        run_scheduled_scan(max_episodes)
                    except Exception as e:
                        add_scheduler_log(f"❌ 掃描錯誤：{str(e)}", 'error')
            
            time.sleep(30)  # 每 30 秒檢查一次
            
            # 檢查並處理待傳佇列（SMB 重連後自動補傳）
            try:
                process_pending_uploads()
            except Exception as e:
                add_scheduler_log(f"⚠️ 補傳檢查錯誤：{str(e)}", 'warning')
            
        except Exception as e:
            add_scheduler_log(f"❌ 排程線程錯誤：{str(e)}", 'error')
            time.sleep(60)

def run_scheduled_scan(max_episodes: int):
    """執行排程掃描：檢查每個 feed 的最新集數並下載"""
    import requests as req
    import feedparser
    
    p = get_pipeline()
    feeds = load_feeds()
    metadata = load_episode_metadata()
    
    for feed in feeds:
        if not feed.get('enabled', True):
            continue
        
        feed_name = feed.get('name', '')
        feed_prefix = feed.get('prefix', '')
        feed_url = feed.get('url', '')
        
        if not feed_url:
            continue
        
        add_scheduler_log(f"🔍 掃描 {feed_name}...")
        
        try:
            # 解析 RSS
            parsed = feedparser.parse(feed_url)
            entries = parsed.entries[:max_episodes]
            
            downloaded = 0
            for i, entry in enumerate(entries):
                # 組裝檔名
                ep_index = len(parsed.entries) - i
                if feed_prefix:
                    file_stem = f"{feed_prefix}_EP{ep_index:03d}"
                else:
                    file_stem = f"EP{ep_index:03d}"
                
                # 檢查是否已下載
                if file_stem in metadata:
                    continue
                
                # 取得音檔 URL
                audio_url = None
                for link in entry.get('links', []):
                    if 'audio' in link.get('type', ''):
                        audio_url = link.get('href')
                        break
                if not audio_url and entry.get('enclosures'):
                    audio_url = entry.enclosures[0].get('href')
                
                if not audio_url:
                    continue
                
                # 下載
                add_scheduler_log(f"   📥 下載 {file_stem}...")
                
                download_dir = Path.home() / 'Downloads' / 'Podcasts'
                download_dir.mkdir(parents=True, exist_ok=True)
                filepath = download_dir / f"{file_stem}.mp3"
                
                if not filepath.exists():
                    resp = req.get(audio_url, stream=True, timeout=300)
                    resp.raise_for_status()
                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)
                
                # 儲存 metadata
                published = entry.get('published', '')
                if published:
                    from email.utils import parsedate_to_datetime
                    try:
                        dt = parsedate_to_datetime(published)
                        published = dt.strftime('%Y-%m-%d')
                    except:
                        pass
                
                metadata[file_stem] = {
                    'feed_name': feed_name,
                    'feed_prefix': feed_prefix,
                    'index': ep_index,
                    'title': entry.get('title', ''),
                    'published': published,
                    'audio_url': audio_url
                }
                save_episode_metadata(metadata)
                
                # 提交給 Whisper
                if p.whisper.is_connected():
                    p.whisper.submit_audio(filepath, f"{file_stem}.mp3")
                    add_scheduler_log(f"   ✅ {file_stem} 已下載並提交", 'success')
                else:
                    # SMB 斷線，加入待傳佇列
                    add_to_pending(str(filepath), f"{file_stem}.mp3")
                    add_scheduler_log(f"   ⏳ {file_stem} 已下載，等待 SMB 重連後自動補傳", 'warning')
                
                downloaded += 1
            
            if downloaded > 0:
                add_scheduler_log(f"   📊 {feed_name} 下載了 {downloaded} 集", 'success')
            else:
                add_scheduler_log(f"   ✓ {feed_name} 無新集數")
                
        except Exception as e:
            add_scheduler_log(f"   ❌ {feed_name} 錯誤：{str(e)}", 'error')


DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎙️ Podcast Pipeline</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root{--bg:#0f0f14;--card:#1a1a24;--hover:#252532;--accent:#6366f1;--success:#10b981;--warning:#f59e0b;--error:#ef4444;--text:#f8fafc;--muted:#64748b;--border:#2a2a3a}
        *{box-sizing:border-box;margin:0;padding:0}
        body{font-family:'Noto Sans TC',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
        .app{display:flex;height:100vh}
        .sidebar{width:220px;background:var(--card);border-right:1px solid var(--border);padding:16px;display:flex;flex-direction:column}
        .logo{display:flex;align-items:center;gap:10px;margin-bottom:24px;padding:8px}
        .logo-icon{width:36px;height:36px;background:linear-gradient(135deg,var(--accent),#a855f7);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px}
        .nav-item{padding:10px 14px;border-radius:8px;cursor:pointer;margin-bottom:4px;display:flex;align-items:center;gap:8px;font-size:13px;transition:all .2s}
        .nav-item:hover{background:var(--hover)}
        .nav-item.active{background:var(--accent)}
        .status-section{margin-top:auto;padding-top:16px;border-top:1px solid var(--border);font-size:11px}
        .status-item{display:flex;align-items:center;gap:6px;padding:5px 0}
        .status-dot{width:6px;height:6px;border-radius:50%}
        .status-dot.on{background:var(--success);box-shadow:0 0 6px var(--success)}
        .status-dot.off{background:var(--error)}
        .main{flex:1;display:flex;flex-direction:column;overflow:hidden}
        .header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
        .header h2{font-size:16px;flex:1}
        .content{flex:1;overflow-y:auto;padding:20px}
        .input-row{display:flex;gap:10px;margin-bottom:14px}
        .input{flex:1;padding:10px 14px;background:var(--card);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px}
        .input:focus{outline:none;border-color:var(--accent)}
        .btn{padding:8px 14px;border:none;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;transition:all .2s;display:inline-flex;align-items:center;gap:5px}
        .btn-primary{background:var(--accent);color:white}
        .btn-secondary{background:var(--hover);color:var(--text)}
        .btn-success{background:var(--success);color:white}
        .btn-danger{background:var(--error);color:white}
        .btn-sm{padding:5px 8px;font-size:11px}
        .card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:14px}
        .table-header{display:flex;align-items:center;padding:8px 12px;background:var(--card);border-radius:6px 6px 0 0;border:1px solid var(--border);border-bottom:none;gap:10px;font-size:11px;color:var(--muted)}
        .episode-list{max-height:280px;overflow-y:auto;border:1px solid var(--border);border-radius:0 0 6px 6px}
        .ep-row{display:flex;align-items:center;padding:10px 12px;border-bottom:1px solid var(--border);gap:10px;transition:background .2s;cursor:pointer;font-size:12px}
        .ep-row:hover{background:var(--hover)}
        .ep-row.selected{background:rgba(99,102,241,.15)}
        .ep-row .checkbox{width:14px;height:14px;accent-color:var(--accent)}
        .ep-row .ep{width:45px;font-family:'JetBrains Mono';color:var(--accent);font-size:10px}
        .ep-row .title{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .ep-row .date{width:70px;text-align:right;color:var(--muted);font-size:10px}
        .actions-bar{display:flex;gap:8px;margin:12px 0;align-items:center;flex-wrap:wrap}
        .selected-count{font-size:12px;color:var(--muted);margin-right:auto}
        .template-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px}
        .template-card{padding:10px;background:var(--card);border:2px solid var(--border);border-radius:6px;cursor:pointer;transition:all .2s;text-align:center}
        .template-card:hover{border-color:var(--accent)}
        .template-card.selected{border-color:var(--accent);background:rgba(99,102,241,.1)}
        .template-card .icon{font-size:18px;margin-bottom:4px}
        .template-card .name{font-weight:600;font-size:11px}
        .log-box{max-height:200px;overflow-y:auto;font-family:'JetBrains Mono';font-size:10px;padding:10px;background:var(--bg);border-radius:6px}
        .log-line{padding:2px 0;color:var(--muted)}
        .log-line.success{color:var(--success)}
        .log-line.error{color:var(--error)}
        .watcher-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:14px}
        .watcher-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
        .watcher-status{display:flex;align-items:center;gap:6px;font-size:12px}
        .watcher-status .dot{width:8px;height:8px;border-radius:50%}
        .watcher-status .dot.running{background:var(--success);animation:pulse 2s infinite}
        .watcher-status .dot.stopped{background:var(--error)}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
        .stats-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}
        .stat-card{background:var(--bg);border-radius:6px;padding:12px;text-align:center}
        .stat-value{font-size:20px;font-weight:700;color:var(--accent)}
        .stat-label{font-size:10px;color:var(--muted);margin-top:4px}
        .feed-item{display:flex;align-items:center;gap:10px;padding:12px;background:var(--card);border:1px solid var(--border);border-radius:6px;margin-bottom:6px}
        .feed-item .icon{font-size:18px}
        .feed-item .info{flex:1;min-width:0}
        .feed-item .name{font-weight:600;font-size:13px}
        .feed-item .url{font-size:10px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .feed-item .meta{display:flex;gap:6px;margin-top:4px;font-size:10px}
        .feed-item .badge{padding:2px 5px;border-radius:3px;background:var(--hover)}
        .modal{position:fixed;inset:0;background:rgba(0,0,0,.7);display:none;align-items:center;justify-content:center;z-index:100}
        .modal.show{display:flex}
        .modal-content{background:var(--card);border-radius:10px;padding:20px;width:450px;max-width:90%}
        .modal-title{font-size:15px;font-weight:600;margin-bottom:14px}
        .form-group{margin-bottom:12px}
        .form-group label{display:block;font-size:11px;color:var(--muted);margin-bottom:5px}
        .form-group .input{width:100%}
        .modal-footer{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}
        .toast{position:fixed;bottom:20px;right:20px;padding:12px 18px;background:var(--card);border:1px solid var(--border);border-radius:6px;display:none;z-index:1000;font-size:12px}
        .toast.show{display:block;animation:slideIn .3s}
        @keyframes slideIn{from{transform:translateX(100px);opacity:0}to{transform:translateX(0);opacity:1}}
        .summary-item{padding:12px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .2s}
        .summary-item:hover{background:var(--hover)}
        .summary-item .name{font-weight:600;margin-bottom:3px;font-size:12px}
        .summary-item .preview{font-size:11px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .schedule-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-top:16px}
        .schedule-row{display:flex;align-items:center;gap:12px;margin-bottom:10px}
        .load-more-btn{width:100%;padding:10px;text-align:center;color:var(--accent);cursor:pointer;font-size:12px;border-top:1px solid var(--border)}
        .load-more-btn:hover{background:var(--hover)}
    </style>
</head>
<body>
    <div class="app">
        <aside class="sidebar">
            <div class="logo"><div class="logo-icon">🎙️</div><div><h1 style="font-size:15px;">Pipeline</h1></div></div>
            <nav>
                <div class="nav-item active" onclick="showPage('download')">📥 下載處理</div>
                <div class="nav-item" onclick="showPage('feeds')">📡 RSS 訂閱</div>
                <div class="nav-item" onclick="showPage('templates')">📝 模板設定</div>
                <div class="nav-item" onclick="showPage('watcher')">🔄 自動監控</div>
                <div class="nav-item" onclick="showPage('summaries')">📋 摘要列表</div>
            </nav>
            <div class="status-section">
                <div class="status-item"><span class="status-dot" id="whisperDot"></span><span>Whisper</span></div>
                <div class="status-item"><span class="status-dot" id="ollamaDot"></span><span>Ollama</span></div>
                <div class="status-item"><span class="status-dot" id="telegramDot"></span><span>Telegram</span></div>
            </div>
        </aside>
        <main class="main">
            <header class="header"><h2 id="pageTitle">📥 下載處理</h2><span id="feedInfo" style="color:var(--muted);font-size:12px;"></span></header>
            <div class="content">
                <!-- Download Page -->
                <div id="page-download">
                    <div class="input-row">
                        <select class="input" id="feedSelect" style="width:180px;" onchange="selectFeed()"></select>
                        <input type="text" class="input" id="rssUrl" placeholder="或輸入 RSS URL...">
                        <button class="btn btn-primary" onclick="loadRSS()">載入</button>
                    </div>
                    <div class="table-header">
                        <input type="checkbox" class="checkbox" id="selectAll" onchange="toggleAll()">
                        <span style="width:45px;">集數</span><span style="flex:1;">標題</span><span style="width:70px;text-align:right;">日期</span>
                    </div>
                    <div class="episode-list" id="episodeList"><div style="padding:25px;text-align:center;color:var(--muted);font-size:12px;">請選擇或輸入 RSS</div></div>
                    <div id="loadMoreContainer" style="display:none;"><div class="load-more-btn" onclick="loadMoreEpisodes()">📥 載入更多集數（目前顯示 <span id="displayCount">0</span>/<span id="totalCount">0</span>）</div></div>
                    <div class="actions-bar">
                        <span class="selected-count" id="selectedCount">已選: 0</span>
                        <button class="btn btn-secondary btn-sm" onclick="selectAll()">全選</button>
                        <button class="btn btn-secondary btn-sm" onclick="selectLatest(5)">最新5集</button>
                        <button class="btn btn-secondary btn-sm" onclick="selectLatest(10)">最新10集</button>
                        <button class="btn btn-secondary btn-sm" onclick="clearSelection()">清除</button>
                    </div>
                    <div class="template-grid">
                        <div class="template-card selected" onclick="selectTemplate('stock_analysis',this)"><div class="icon">📈</div><div class="name">股票財經</div></div>
                        <div class="template-card" onclick="selectTemplate('default',this)"><div class="icon">📝</div><div class="name">通用</div></div>
                        <div class="template-card" onclick="selectTemplate('news',this)"><div class="icon">📰</div><div class="name">新聞</div></div>
                        <div class="template-card" onclick="selectTemplate('tech',this)"><div class="icon">🚀</div><div class="name">科技</div></div>
                    </div>
                    <button class="btn btn-success" style="width:100%;" onclick="startBatch()">🚀 開始批次下載</button>
                    <div class="card" id="progressCard" style="display:none;margin-top:14px;"><div style="font-size:12px;font-weight:600;margin-bottom:8px;">📜 處理日誌</div><div class="log-box" id="progressLog"></div></div>
                </div>
                <!-- Feeds Page -->
                <div id="page-feeds" style="display:none;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <h3 style="font-size:14px;">📡 已訂閱的 RSS Feed</h3>
                        <button class="btn btn-primary btn-sm" onclick="showAddFeedModal()">+ 新增訂閱</button>
                    </div>
                    <div id="feedList"></div>
                    <div class="schedule-card">
                        <div style="font-size:13px;font-weight:600;margin-bottom:12px;">⏰ 排程掃描設定</div>
                        <div class="schedule-row">
                            <label style="font-size:12px;"><input type="checkbox" id="scheduleEnabled" style="margin-right:6px;"> 啟用每日自動掃描</label>
                        </div>
                        <div class="schedule-row">
                            <label style="font-size:11px;width:80px;">掃描時間</label>
                            <input type="text" class="input" id="scheduleTimes" placeholder="08:00, 12:00, 20:00" style="width:200px;">
                        </div>
                        <div style="font-size:10px;color:var(--muted);margin-left:80px;margin-bottom:8px;">多個時間用逗號分隔，如 08:00, 20:00</div>
                        <div class="schedule-row">
                            <label style="font-size:11px;width:80px;">下載集數</label>
                            <input type="number" class="input" id="scheduleMax" value="5" min="1" max="50" style="width:80px;">
                            <span style="font-size:11px;color:var(--muted);">每次掃描最新 N 集</span>
                        </div>
                        <button class="btn btn-primary btn-sm" onclick="saveSchedule()" style="margin-top:8px;">儲存設定</button>
                    </div>
                </div>
                <!-- Watcher Page -->
                <div id="page-watcher" style="display:none;">
                    <div class="watcher-card">
                        <div class="watcher-header">
                            <div class="watcher-status"><span class="dot" id="watcherDot"></span><span id="watcherText">已停止</span></div>
                            <div style="display:flex;gap:8px;align-items:center;">
                                <label style="font-size:11px;display:flex;align-items:center;gap:4px;cursor:pointer;" title="關閉時不會推送到 Telegram">
                                    <input type="checkbox" id="tgBroadcastToggle" checked onchange="toggleTgBroadcast()">
                                    📤 TG廣播
                                </label>
                                <button class="btn btn-success btn-sm" id="btnStart" onclick="startWatcher()">▶️ 啟動</button>
                                <button class="btn btn-danger btn-sm" id="btnStop" onclick="stopWatcher()" style="display:none;">⏹️ 停止</button>
                            </div>
                        </div>
                        <div class="stats-grid">
                            <div class="stat-card"><div class="stat-value" id="statProcessed">0</div><div class="stat-label">已處理</div></div>
                            <div class="stat-card"><div class="stat-value" id="statPending">0</div><div class="stat-label">待處理</div></div>
                            <div class="stat-card"><div class="stat-value" id="statLastCheck">--:--</div><div class="stat-label">最後檢查</div></div>
                        </div>
                        <div style="margin-bottom:8px;color:var(--muted);font-size:11px;">⚠️ 已排除 S3EP* 開頭的檔案</div>
                        <div class="log-box" id="watcherLog" style="height:150px;"></div>
                    </div>
                    <!-- 排程日誌 -->
                    <div class="watcher-card" style="margin-top:16px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                            <h4 style="font-size:13px;margin:0;">📅 排程掃描日誌</h4>
                            <span id="schedulerLastRun" style="font-size:11px;color:var(--muted);"></span>
                        </div>
                        <div class="log-box" id="schedulerLog" style="height:100px;"></div>
                    </div>
                </div>
                <!-- Templates Page -->
                <div id="page-templates" style="display:none;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <h3 style="font-size:14px;">📝 摘要模板設定</h3>
                        <button class="btn btn-primary btn-sm" onclick="showNewTemplateModal()">+ 新增模板</button>
                    </div>
                    <div id="templateList" style="display:grid;gap:12px;"></div>
                </div>
                <!-- Summaries Page -->
                <div id="page-summaries" style="display:none;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                        <h3 style="font-size:14px;">📋 已生成的摘要</h3>
                        <div style="display:flex;gap:8px;align-items:center;">
                            <button class="btn btn-primary btn-sm" id="btnBatchSend" onclick="batchSendToTelegram()" style="display:none;">📤 發送選中 (<span id="selectedCount">0</span>)</button>
                            <label style="font-size:11px;cursor:pointer;"><input type="checkbox" id="selectAllSummaries" onchange="toggleSelectAll()"> 全選</label>
                            <button class="btn btn-secondary btn-sm" onclick="loadSummaries()">重新載入</button>
                        </div>
                    </div>
                    <div class="card" style="padding:0;"><div class="summary-list" id="summaryList" style="max-height:450px;overflow-y:auto;"></div></div>
                </div>
            </div>
        </main>
    </div>
    <!-- Add Feed Modal -->
    <div class="modal" id="addFeedModal">
        <div class="modal-content">
            <div class="modal-title">📡 新增 RSS 訂閱</div>
            <div class="form-group"><label>名稱（自訂顯示名稱）</label><input type="text" class="input" id="newFeedName" placeholder="例如：財報狗"></div>
            <div class="form-group"><label>節目縮寫（用於檔名前綴，避免集數衝突）</label><input type="text" class="input" id="newFeedPrefix" placeholder="例如：CFG、MDJ" maxlength="10"></div>
            <div class="form-group"><label>RSS URL</label><input type="text" class="input" id="newFeedUrl" placeholder="https://..."></div>
            <div class="form-group"><label>預設模板</label><select class="input" id="newFeedTemplate"><option value="stock_analysis">股票財經</option><option value="default">通用</option><option value="news">新聞</option><option value="tech">科技</option></select></div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="addFeed()">新增</button>
            </div>
        </div>
    </div>
    <!-- Template Edit Modal -->
    <div class="modal" id="templateModal">
        <div class="modal-content" style="width:700px;max-width:95vw;">
            <div class="modal-title" id="templateModalTitle">📝 編輯模板</div>
            <input type="hidden" id="editTemplateId">
            <div class="form-group"><label>模板名稱</label><input type="text" class="input" id="editTemplateName" placeholder="例如：財報狗專屬"></div>
            <div class="form-group"><label>描述</label><input type="text" class="input" id="editTemplateDesc" placeholder="描述這個模板的用途"></div>
            <div class="form-group"><label>潤稿提示詞（polish_prompt）</label><textarea class="input" id="editPolishPrompt" rows="6" style="font-family:monospace;font-size:11px;" placeholder="用於潤飾逐字稿的 prompt..."></textarea></div>
            <div class="form-group"><label>摘要提示詞（summary_prompt）</label><textarea class="input" id="editSummaryPrompt" rows="12" style="font-family:monospace;font-size:11px;" placeholder="用於生成摘要的 prompt..."></textarea></div>
            <div style="font-size:10px;color:var(--muted);margin-bottom:10px;">💡 可用變數：{transcript} = 逐字稿、{episode_title} = 集數標題</div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeTemplateModal()">取消</button>
                <button class="btn btn-primary" onclick="saveTemplate()">儲存</button>
            </div>
        </div>
    </div>
    <div class="toast" id="toast"></div>
    <script>
        let episodes=[], feeds=[], selectedTemplate='stock_analysis', currentFeedName='', currentFeedPrefix='';
        let displayLimit = 30;
        
        async function loadStatus() {
            try {
                const r=await fetch('/api/status');
                const d=await r.json();
                document.getElementById('whisperDot').className='status-dot '+(d.whisper.connected?'on':'off');
                document.getElementById('ollamaDot').className='status-dot '+(d.ollama.local.fallback.connected||d.ollama.local.primary.connected?'on':'off');
                document.getElementById('telegramDot').className='status-dot '+(d.telegram&&d.telegram.connected?'on':'off');
            } catch(e) { console.error(e); }
        }
        
        async function loadFeeds() {
            try {
                const r=await fetch('/api/feeds');
                feeds=await r.json();
                renderFeedSelect();
                renderFeedList();
            } catch(e) { console.error(e); }
        }
        
        function renderFeedSelect() {
            const sel=document.getElementById('feedSelect');
            sel.innerHTML='<option value="">-- 選擇已訂閱 --</option>'+feeds.map(f=>`<option value="${f.url}" data-name="${f.name}" data-prefix="${f.prefix||''}">${f.name}</option>`).join('');
        }
        
        function renderFeedList() {
            const list=document.getElementById('feedList');
            if (!feeds || feeds.length === 0) {
                list.innerHTML='<div style="padding:25px;text-align:center;color:var(--muted);font-size:12px;">尚未新增任何訂閱</div>';
                return;
            }
            // 建立模板選項
            const templateOptions = Object.entries(templates).map(([id, t]) => 
                `<option value="${id}">${t.name}</option>`
            ).join('');
            
            list.innerHTML=feeds.map((f,i)=>`
                <div class="feed-item">
                    <div class="icon">📡</div>
                    <div class="info">
                        <div class="name">${f.name || '未命名'}${f.prefix ? ' ['+f.prefix+']' : ''}</div>
                        <div class="url">${f.url || ''}</div>
                        <div class="meta" style="display:flex;align-items:center;gap:8px;margin-top:6px;">
                            <span class="badge">縮寫: ${f.prefix||'無'}</span>
                            <select class="input" style="width:160px;height:26px;font-size:11px;padding:2px 6px;" onchange="updateFeedTemplate(${i}, this.value)">
                                ${Object.entries(templates).map(([id, t]) => 
                                    `<option value="${id}" ${(f.template||'stock_analysis')===id?'selected':''}>${t.name}</option>`
                                ).join('')}
                            </select>
                        </div>
                    </div>
                    <button class="btn btn-danger btn-sm" onclick="deleteFeed(${i}); event.stopPropagation();">刪除</button>
                </div>
            `).join('');
        }
        
        async function updateFeedTemplate(index, templateId) {
            if (feeds[index]) {
                feeds[index].template = templateId;
                await fetch('/api/feeds/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(feeds)
                });
                showToast(`${feeds[index].name} 的模板已更改為 ${templates[templateId]?.name || templateId}`, 'success');
            }
        }
        
        function selectFeed() {
            const sel=document.getElementById('feedSelect');
            const opt=sel.options[sel.selectedIndex];
            if(sel.value) {
                document.getElementById('rssUrl').value=sel.value;
                currentFeedName=opt.dataset.name||'';
                currentFeedPrefix=opt.dataset.prefix||'';
            }
        }
        
        async function loadRSS() {
            const url=document.getElementById('rssUrl').value;
            if(!url)return;
            document.getElementById('episodeList').innerHTML='<div style="padding:25px;text-align:center;color:var(--muted);font-size:12px;">載入中...</div>';
            try {
                const r=await fetch('/api/parse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
                const d=await r.json();
                if(d.error){showToast(d.error,'error');return;}
                episodes=d.episodes;
                if(!currentFeedName)currentFeedName=d.title;
                document.getElementById('feedInfo').textContent=`${d.title} — ${episodes.length} 集`;
                displayLimit = 30;
                renderEpisodes();
                showToast('載入成功！','success');
            } catch(e) { showToast('載入失敗','error'); }
        }
        
        function renderEpisodes() {
            const list=document.getElementById('episodeList');
            const recent = episodes.slice(-displayLimit).reverse();
            list.innerHTML=recent.map(ep=>`<div class="ep-row" onclick="toggleEp(${ep.index},this)"><input type="checkbox" class="checkbox" data-index="${ep.index}" onclick="event.stopPropagation();updateCount();"><span class="ep">EP${String(ep.index).padStart(3,'0')}</span><span class="title">${ep.title}</span><span class="date">${ep.published}</span></div>`).join('');
            
            // 載入更多按鈕
            const container = document.getElementById('loadMoreContainer');
            if (episodes.length > displayLimit) {
                container.style.display = 'block';
                document.getElementById('displayCount').textContent = displayLimit;
                document.getElementById('totalCount').textContent = episodes.length;
            } else {
                container.style.display = 'none';
            }
            updateCount();
        }
        
        function loadMoreEpisodes() {
            displayLimit += 30;
            if (displayLimit > episodes.length) displayLimit = episodes.length;
            renderEpisodes();
        }
        
        function toggleEp(i,row){const cb=row.querySelector('input');cb.checked=!cb.checked;row.classList.toggle('selected',cb.checked);updateCount();}
        function toggleAll(){const c=document.getElementById('selectAll').checked;document.querySelectorAll('.ep-row').forEach(r=>{r.querySelector('input').checked=c;r.classList.toggle('selected',c);});updateCount();}
        function selectAll(){document.querySelectorAll('.ep-row').forEach(r=>{r.querySelector('input').checked=true;r.classList.add('selected');});document.getElementById('selectAll').checked=true;updateCount();}
        function selectLatest(n){document.querySelectorAll('.ep-row').forEach((r,i)=>{const c=i<n;r.querySelector('input').checked=c;r.classList.toggle('selected',c);});updateCount();}
        function clearSelection(){document.querySelectorAll('.ep-row').forEach(r=>{r.querySelector('input').checked=false;r.classList.remove('selected');});document.getElementById('selectAll').checked=false;updateCount();}
        function updateCount(){document.getElementById('selectedCount').textContent='已選: '+document.querySelectorAll('.ep-row input:checked').length;}
        function selectTemplate(t,el){selectedTemplate=t;document.querySelectorAll('.template-card').forEach(c=>c.classList.remove('selected'));el.classList.add('selected');}
        function getSelected(){const ids=[];document.querySelectorAll('.ep-row input:checked').forEach(cb=>ids.push(+cb.dataset.index));return episodes.filter(e=>ids.includes(e.index));}
        
        async function startBatch() {
            const sel=getSelected();if(!sel.length){showToast('請選擇集數','error');return;}
            // 保存當前 feed 資訊，避免下載中途被新 RSS 覆蓋
            const batchFeedName = currentFeedName;
            const batchFeedPrefix = currentFeedPrefix;
            const card=document.getElementById('progressCard'),log=document.getElementById('progressLog');
            card.style.display='block';log.innerHTML='';
            addLog(`📡 開始下載 ${batchFeedName || 'RSS'} 的 ${sel.length} 集...`);
            for(let i=0;i<sel.length;i++){
                const ep=sel[i];
                const filePrefix = batchFeedPrefix ? batchFeedPrefix+'_EP'+String(ep.index).padStart(3,'0') : 'EP'+String(ep.index).padStart(3,'0');
                addLog(`[${i+1}/${sel.length}] ${filePrefix}: ${ep.title.slice(0,30)}...`);
                try{
                    addLog('  📥 下載中...');
                    const r=await fetch('/api/download_and_copy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({episode:ep,feed_name:batchFeedName,feed_prefix:batchFeedPrefix})});
                    const d=await r.json();
                    if(d.success) addLog('  ✅ 完成 → '+d.file_stem,'success');
                    else addLog('  ❌ '+d.error,'error');
                }catch(e){addLog('  ❌ '+e.message,'error');}
            }
            addLog('🎉 批次完成！','success');
        }
        
        function addLog(m,l){const log=document.getElementById('progressLog');log.innerHTML+=`<div class="log-line ${l||''}">${m}</div>`;log.scrollTop=log.scrollHeight;}
        
        function showAddFeedModal(){document.getElementById('addFeedModal').classList.add('show');}
        function closeModal(){document.querySelectorAll('.modal').forEach(m=>m.classList.remove('show'));}
        
        async function addFeed() {
            const name=document.getElementById('newFeedName').value;
            const prefix=document.getElementById('newFeedPrefix').value.toUpperCase().replace(/[^A-Z0-9]/g,'');
            const url=document.getElementById('newFeedUrl').value;
            const template=document.getElementById('newFeedTemplate').value;
            if(!name||!url){showToast('請填寫名稱和 URL','error');return;}
            try {
                const r=await fetch('/api/feeds/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,prefix,url,template})});
                const d=await r.json();
                if(d.ok){closeModal();await loadFeeds();showToast('新增成功！','success');}
            } catch(e) { showToast('新增失敗','error'); }
        }
        
        async function deleteFeed(i) {
            if(!confirm('確定要刪除此訂閱？'))return;
            try {
                await fetch('/api/feeds/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i})});
                await loadFeeds();
                showToast('已刪除','success');
            } catch(e) { showToast('刪除失敗','error'); }
        }
        
        async function saveSchedule() {
            const timesStr = document.getElementById('scheduleTimes').value;
            const times = timesStr.split(',').map(t => t.trim()).filter(t => /^\d{1,2}:\d{2}$/.test(t));
            const config = {
                enabled: document.getElementById('scheduleEnabled').checked,
                times: times.length > 0 ? times : ['20:00'],
                max_episodes: parseInt(document.getElementById('scheduleMax').value) || 5
            };
            await fetch('/api/schedule/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
            showToast(`排程已設定為 ${times.join(', ') || '20:00'}`,'success');
        }
        
        async function loadSchedule() {
            try {
                const r = await fetch('/api/schedule');
                const d = await r.json();
                document.getElementById('scheduleEnabled').checked = d.enabled || false;
                // 支援新舊格式
                const times = d.times || (d.time ? [d.time] : ['20:00']);
                document.getElementById('scheduleTimes').value = times.join(', ');
                document.getElementById('scheduleMax').value = d.max_episodes || 5;
            } catch(e) {}
        }
        
        async function startWatcher(){await fetch('/api/watcher/start',{method:'POST'});updateWatcherUI(true);pollWatcher();}
        async function stopWatcher(){await fetch('/api/watcher/stop',{method:'POST'});updateWatcherUI(false);}
        function updateWatcherUI(running){
            document.getElementById('watcherDot').className='dot '+(running?'running':'stopped');
            document.getElementById('watcherText').textContent=running?'運行中':'已停止';
            document.getElementById('btnStart').style.display=running?'none':'inline-flex';
            document.getElementById('btnStop').style.display=running?'inline-flex':'none';
        }
        async function pollWatcher(){
            if(document.getElementById('btnStop').style.display==='none')return;
            try {
                const r=await fetch('/api/watcher/status');const d=await r.json();
                document.getElementById('statProcessed').textContent=d.processed_count;
                document.getElementById('statPending').textContent=d.pending_count||0;
                document.getElementById('statLastCheck').textContent=d.last_check||'--:--';
                const log=document.getElementById('watcherLog');
                log.innerHTML=d.logs.map(l=>`<div class="log-line ${l.level}">[${l.time}] ${l.msg}</div>`).join('');
                log.scrollTop=log.scrollHeight;
                
                // 載入排程日誌
                if (d.scheduler_logs) {
                    const slog = document.getElementById('schedulerLog');
                    slog.innerHTML = d.scheduler_logs.map(l=>`<div class="log-line ${l.level}">[${l.time}] ${l.msg}</div>`).join('');
                    slog.scrollTop = slog.scrollHeight;
                }
                if (d.scheduler_last_run) {
                    document.getElementById('schedulerLastRun').textContent = '上次執行：' + d.scheduler_last_run;
                }
                
                if(d.running)setTimeout(pollWatcher,3000);else updateWatcherUI(false);
            } catch(e) {}
        }
        
        // Telegram 廣播開關
        async function toggleTgBroadcast() {
            const enabled = document.getElementById('tgBroadcastToggle').checked;
            try {
                await fetch('/api/telegram/broadcast', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ enabled })
                });
                showToast(enabled ? '📤 Telegram 廣播已開啟' : '📴 Telegram 廣播已關閉', enabled ? 'success' : 'warning');
            } catch(e) { console.error(e); }
        }
        
        async function loadTgBroadcastStatus() {
            try {
                const r = await fetch('/api/telegram/broadcast');
                const d = await r.json();
                document.getElementById('tgBroadcastToggle').checked = d.enabled;
            } catch(e) {}
        }
        
        async function loadSummaries(){
            try {
                const r=await fetch('/api/summaries');const d=await r.json();
                document.getElementById('summaryList').innerHTML=d.map(s=>`
                    <div class="summary-item" style="display:flex;align-items:flex-start;gap:10px;">
                        <input type="checkbox" class="summary-checkbox" data-name="${s.name}" onchange="updateSelectedCount()" style="margin-top:4px;cursor:pointer;">
                        <div style="flex:1;cursor:pointer;" onclick="window.open('/api/summary/${s.name}','_blank')">
                            <div class="name">${s.name}</div>
                            <div class="preview">${s.preview}</div>
                        </div>
                    </div>
                `).join('')||'<div style="padding:25px;text-align:center;color:var(--muted);font-size:12px;">尚無摘要</div>';
                updateSelectedCount();
            } catch(e) {}
        }
        
        function updateSelectedCount() {
            const checkboxes = document.querySelectorAll('.summary-checkbox:checked');
            const count = checkboxes.length;
            document.getElementById('selectedCount').textContent = count;
            document.getElementById('btnBatchSend').style.display = count > 0 ? 'inline-flex' : 'none';
        }
        
        function toggleSelectAll() {
            const selectAll = document.getElementById('selectAllSummaries').checked;
            document.querySelectorAll('.summary-checkbox').forEach(cb => cb.checked = selectAll);
            updateSelectedCount();
        }
        
        async function batchSendToTelegram() {
            const checkboxes = document.querySelectorAll('.summary-checkbox:checked');
            const names = Array.from(checkboxes).map(cb => cb.dataset.name);
            
            if (names.length === 0) {
                showToast('請先選擇要發送的摘要', 'warning');
                return;
            }
            
            // 按 EP 數字排序（小的先發）
            names.sort((a, b) => {
                const numA = parseInt(a.match(/EP(\d+)/)?.[1] || '0');
                const numB = parseInt(b.match(/EP(\d+)/)?.[1] || '0');
                return numA - numB;
            });
            
            showToast(`開始發送 ${names.length} 個摘要...`, 'info');
            document.getElementById('btnBatchSend').disabled = true;
            
            let success = 0, failed = 0;
            for (const name of names) {
                try {
                    const r = await fetch('/api/telegram/send', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ summary_name: name })
                    });
                    const d = await r.json();
                    if (d.success) {
                        success++;
                        showToast(`✅ 已發送 ${name} (${success}/${names.length})`, 'success');
                    } else {
                        failed++;
                        showToast(`❌ ${name} 發送失敗: ${d.error}`, 'error');
                    }
                    // 間隔 1 秒避免 Telegram 限流
                    await new Promise(r => setTimeout(r, 1000));
                } catch(e) {
                    failed++;
                }
            }
            
            document.getElementById('btnBatchSend').disabled = false;
            showToast(`發送完成！成功 ${success}，失敗 ${failed}`, success > 0 ? 'success' : 'error');
            
            // 取消所有選擇
            document.querySelectorAll('.summary-checkbox').forEach(cb => cb.checked = false);
            document.getElementById('selectAllSummaries').checked = false;
            updateSelectedCount();
        }
        
        // 模板管理函數
        let templates = {};
        
        async function loadTemplates() {
            try {
                const r = await fetch('/api/templates');
                templates = await r.json();
                renderTemplateList();
            } catch(e) { console.error(e); }
        }
        
        function renderTemplateList() {
            const list = document.getElementById('templateList');
            const html = Object.entries(templates).map(([id, t]) => `
                <div class="card" style="padding:12px;">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                        <div>
                            <div style="font-weight:600;font-size:13px;">${t.name}</div>
                            <div style="color:var(--muted);font-size:11px;margin-top:4px;">${t.description || ''}</div>
                            <div style="color:var(--accent);font-size:10px;margin-top:6px;">ID: ${id}</div>
                        </div>
                        <div style="display:flex;gap:6px;">
                            <button class="btn btn-secondary btn-sm" onclick="editTemplate('${id}')">編輯</button>
                            ${!['stock_analysis','default','news','tech'].includes(id) ? `<button class="btn btn-danger btn-sm" onclick="deleteTemplate('${id}')">刪除</button>` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
            list.innerHTML = html || '<div style="text-align:center;color:var(--muted);padding:30px;">無模板</div>';
        }
        
        function editTemplate(id) {
            const t = templates[id];
            document.getElementById('editTemplateId').value = id;
            document.getElementById('editTemplateName').value = t.name || '';
            document.getElementById('editTemplateDesc').value = t.description || '';
            document.getElementById('editPolishPrompt').value = t.polish_prompt || '';
            document.getElementById('editSummaryPrompt').value = t.summary_prompt || '';
            document.getElementById('templateModalTitle').textContent = '📝 編輯模板：' + t.name;
            document.getElementById('templateModal').style.display = 'flex';
        }
        
        function showNewTemplateModal() {
            document.getElementById('editTemplateId').value = '';
            document.getElementById('editTemplateName').value = '';
            document.getElementById('editTemplateDesc').value = '';
            document.getElementById('editPolishPrompt').value = '';
            document.getElementById('editSummaryPrompt').value = '';
            document.getElementById('templateModalTitle').textContent = '📝 新增模板';
            document.getElementById('templateModal').style.display = 'flex';
        }
        
        function closeTemplateModal() {
            document.getElementById('templateModal').style.display = 'none';
        }
        
        async function saveTemplate() {
            const oldId = document.getElementById('editTemplateId').value;
            const name = document.getElementById('editTemplateName').value.trim();
            const description = document.getElementById('editTemplateDesc').value.trim();
            const polish_prompt = document.getElementById('editPolishPrompt').value;
            const summary_prompt = document.getElementById('editSummaryPrompt').value;
            
            if (!name) { showToast('請輸入模板名稱', 'error'); return; }
            
            // 新模板需要生成 ID
            const id = oldId || name.toLowerCase().replace(/[^a-z0-9]/g, '_');
            
            try {
                const r = await fetch('/api/templates/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id, name, description, polish_prompt, summary_prompt })
                });
                const d = await r.json();
                if (d.success) {
                    showToast('模板已儲存', 'success');
                    closeTemplateModal();
                    loadTemplates();
                    updateTemplateSelects();
                } else {
                    showToast(d.error || '儲存失敗', 'error');
                }
            } catch(e) { showToast('儲存失敗', 'error'); }
        }
        
        async function deleteTemplate(id) {
            if (!confirm(`確定要刪除模板「${templates[id]?.name}」嗎？`)) return;
            try {
                const r = await fetch('/api/templates/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                const d = await r.json();
                if (d.success) {
                    showToast('模板已刪除', 'success');
                    loadTemplates();
                    updateTemplateSelects();
                } else {
                    showToast(d.error || '刪除失敗', 'error');
                }
            } catch(e) { showToast('刪除失敗', 'error'); }
        }
        
        function updateTemplateSelects() {
            const sel = document.getElementById('newFeedTemplate');
            sel.innerHTML = Object.entries(templates).map(([id, t]) => 
                `<option value="${id}">${t.name}</option>`
            ).join('');
        }
        
        function showPage(p){
            document.querySelectorAll('.nav-item').forEach((n,i)=>n.classList.toggle('active',['download','feeds','templates','watcher','summaries'][i]===p));
            document.querySelectorAll('[id^="page-"]').forEach(pg=>pg.style.display='none');
            document.getElementById('page-'+p).style.display='block';
            const t={download:'📥 下載處理',feeds:'📡 RSS 訂閱',templates:'📝 模板設定',watcher:'🔄 自動監控',summaries:'📋 摘要列表'};
            document.getElementById('pageTitle').textContent=t[p];
            if(p==='feeds'){loadFeeds();loadSchedule();}
            if(p==='templates')loadTemplates();
            if(p==='watcher'){loadTgBroadcastStatus();fetch('/api/watcher/status').then(r=>r.json()).then(d=>{updateWatcherUI(d.running);if(d.running)pollWatcher();}).catch(()=>{});}
            if(p==='summaries')loadSummaries();
        }
        
        function showToast(m,t){const toast=document.getElementById('toast');toast.textContent=m;toast.className='toast show '+(t||'');setTimeout(()=>toast.className='toast',3000);}
        
        loadStatus();loadFeeds();loadTemplates();
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def api_status():
    p = get_pipeline()
    status = p.get_status()
    
    # 加入 Telegram 狀態
    telegram_config = load_telegram_config()
    telegram_connected = False
    if telegram_config.get('enabled') and telegram_config.get('bot_token') and telegram_config.get('chat_id'):
        try:
            import requests
            resp = requests.get(
                f"https://api.telegram.org/bot{telegram_config['bot_token']}/getMe",
                timeout=5
            )
            telegram_connected = resp.ok and resp.json().get('ok', False)
        except:
            pass
    
    status['telegram'] = {
        'enabled': telegram_config.get('enabled', False),
        'connected': telegram_connected,
        'chat_id': telegram_config.get('chat_id', '')
    }
    
    return jsonify(status)

@app.route('/api/feeds')
def api_feeds():
    return jsonify(load_feeds())

@app.route('/api/feeds/add', methods=['POST'])
def api_feeds_add():
    try:
        data = request.json
        feeds = load_feeds()
        feeds.append({
            'name': data['name'],
            'url': data['url'],
            'enabled': True,
            'prefix': data.get('prefix', ''),  # 節目縮寫（如 CFG、MDJ）
            'filename_pattern': data.get('filename_pattern', 'EP{index:03d}'),
            'template': data.get('template', 'stock_analysis')
        })
        save_feeds(feeds)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/feeds/delete', methods=['POST'])
def api_feeds_delete():
    try:
        idx = request.json.get('index', -1)
        feeds = load_feeds()
        if 0 <= idx < len(feeds):
            feeds.pop(idx)
            save_feeds(feeds)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/schedule')
def api_schedule():
    return jsonify(load_schedule_config())

@app.route('/api/schedule/save', methods=['POST'])
def api_schedule_save():
    try:
        config = request.json
        save_schedule_config(config)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/parse', methods=['POST'])
def api_parse():
    try:
        url = request.json.get('url')
        info = parse_rss(url)
        episodes = [{'index': ep.index, 'title': ep.title, 'published': ep.published.strftime('%Y-%m-%d'), 'audio_url': ep.audio_url} for ep in info.episodes]
        return jsonify({'title': info.title, 'episodes': episodes})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/download_and_copy', methods=['POST'])
def api_download_and_copy():
    try:
        ep = request.json.get('episode')
        feed_name = request.json.get('feed_name', '')
        feed_prefix = request.json.get('feed_prefix', '')  # 節目縮寫
        p = get_pipeline()
        import requests as req
        
        download_dir = Path.home() / 'Downloads' / 'Podcasts'
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用「節目縮寫_EPxxx」格式避免衝突
        if feed_prefix:
            file_stem = f"{feed_prefix}_EP{ep['index']:03d}"
        else:
            file_stem = f"EP{ep['index']:03d}"
        
        filename = f"{file_stem}.mp3"
        filepath = download_dir / filename
        
        if not filepath.exists():
            resp = req.get(ep['audio_url'], stream=True, timeout=300)
            resp.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
        
        # 儲存 metadata（用於生成摘要標題）
        metadata = load_episode_metadata()
        metadata[file_stem] = {
            'feed_name': feed_name,
            'feed_prefix': feed_prefix,
            'index': ep['index'],
            'title': ep['title'],
            'published': ep.get('published', ''),  # 日期
            'audio_url': ep['audio_url']
        }
        save_episode_metadata(metadata)
        
        if p.whisper.is_connected():
            p.whisper.submit_audio(filepath, filename)
            return jsonify({'success': True, 'file_stem': file_stem})
        return jsonify({'success': False, 'error': 'Whisper 未連接'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/watcher/start', methods=['POST'])
def api_watcher_start():
    if not watcher_status['running']:
        watcher_status['running'] = True
        watcher_status['logs'] = []
        t = threading.Thread(target=watcher_thread, daemon=True)
        t.start()
    return jsonify({'ok': True})

@app.route('/api/watcher/stop', methods=['POST'])
def api_watcher_stop():
    watcher_status['running'] = False
    return jsonify({'ok': True})

@app.route('/api/watcher/status')
def api_watcher_status():
    p = get_pipeline()
    pending = 0
    try:
        if p.whisper.is_connected():
            # 載入 metadata 來正確關聯
            metadata = load_episode_metadata()
            
            # 取得已處理的 stem（從 metadata key 來判斷）
            processed_stems = set()
            for f in p.summaries_dir.glob('*_summary.md'):
                # 嘗試從 metadata 反查
                for stem, meta in metadata.items():
                    feed_name = meta.get('feed_name', '')
                    ep_index = meta.get('index', '')
                    if feed_name and isinstance(ep_index, int):
                        expected_filename = f'{feed_name}EP{ep_index:03d}_summary.md'
                        if f.name == expected_filename:
                            processed_stems.add(stem)
                            break
                else:
                    # 舊格式：stem_summary.md
                    processed_stems.add(f.stem.replace('_summary', ''))
            
            # 計算待處理
            for t in p.whisper.output_dir.glob('*_tw.txt'):
                stem = t.stem.replace('_tw', '')
                if any(stem.startswith(pf) for pf in EXCLUDE_PREFIXES):
                    continue
                if stem not in processed_stems:
                    # 額外檢查：對應的摘要檔案是否已存在
                    meta = metadata.get(stem, {})
                    feed_name = meta.get('feed_name', '')
                    ep_index = meta.get('index', stem)
                    if feed_name and isinstance(ep_index, int):
                        summary_filename = f'{feed_name}EP{ep_index:03d}_summary.md'
                    else:
                        summary_filename = f'{stem}_summary.md'
                    
                    if not (p.summaries_dir / summary_filename).exists():
                        pending += 1
    except:
        pass
    return jsonify({
        'running': watcher_status['running'],
        'logs': watcher_status['logs'][-50:],
        'processed_count': watcher_status['processed_count'],
        'pending_count': pending,
        'last_check': watcher_status['last_check'],
        'scheduler_logs': scheduler_status.get('logs', [])[-20:],
        'scheduler_last_run': scheduler_status.get('last_run')
    })

@app.route('/api/telegram/broadcast', methods=['GET', 'POST'])
def api_telegram_broadcast():
    global telegram_broadcast_enabled
    if request.method == 'POST':
        data = request.json or {}
        telegram_broadcast_enabled = data.get('enabled', True)
        return jsonify({'ok': True, 'enabled': telegram_broadcast_enabled})
    return jsonify({'enabled': telegram_broadcast_enabled})

@app.route('/api/telegram/send', methods=['POST'])
def api_telegram_send():
    """手動發送單個摘要到 Telegram"""
    try:
        data = request.json or {}
        summary_name = data.get('summary_name', '')
        
        if not summary_name:
            return jsonify({'success': False, 'error': '未指定摘要名稱'})
        
        p = get_pipeline()
        summary_file = p.summaries_dir / f'{summary_name}_summary.md'
        
        if not summary_file.exists():
            return jsonify({'success': False, 'error': f'摘要不存在：{summary_name}'})
        
        telegram_config = load_telegram_config()
        if not telegram_config.get('enabled'):
            return jsonify({'success': False, 'error': 'Telegram 未啟用'})
        
        notifier = TelegramNotifier(telegram_config)
        result = notifier.send_summary(summary_file)
        
        if result.success:
            mark_as_broadcasted(summary_name)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': result.error})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ===== 模板 API =====
def load_templates():
    """載入所有模板"""
    template_file = CONFIG_DIR / 'templates.yaml'
    if template_file.exists():
        with open(template_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return data.get('templates', {})
    return {}

def save_templates(templates):
    """儲存模板"""
    template_file = CONFIG_DIR / 'templates.yaml'
    with open(template_file, 'w', encoding='utf-8') as f:
        yaml.dump({'templates': templates}, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

@app.route('/api/templates')
def api_templates():
    return jsonify(load_templates())

@app.route('/api/templates/save', methods=['POST'])
def api_templates_save():
    try:
        data = request.json
        template_id = data.get('id', '').strip()
        if not template_id:
            return jsonify({'success': False, 'error': '模板 ID 不能為空'})
        
        templates = load_templates()
        templates[template_id] = {
            'name': data.get('name', template_id),
            'description': data.get('description', ''),
            'polish_prompt': data.get('polish_prompt', ''),
            'summary_prompt': data.get('summary_prompt', '')
        }
        save_templates(templates)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/templates/delete', methods=['POST'])
def api_templates_delete():
    try:
        data = request.json
        template_id = data.get('id', '')
        
        # 不允許刪除內建模板
        if template_id in ['stock_analysis', 'default', 'news', 'tech']:
            return jsonify({'success': False, 'error': '不能刪除內建模板'})
        
        templates = load_templates()
        if template_id in templates:
            del templates[template_id]
            save_templates(templates)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '模板不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/summaries')
def api_summaries():
    p = get_pipeline()
    summaries = []
    for f in sorted(p.summaries_dir.glob('*_summary.md'), reverse=True)[:50]:
        content = f.read_text(encoding='utf-8')
        lines = content.split('\n')
        title_line = next((l for l in lines if l.startswith('# ')), '')
        preview = next((l for l in lines if l.strip() and not l.startswith('#')), '')[:100]
        summaries.append({
            'name': f.stem.replace('_summary',''),
            'title': title_line.replace('# ', ''),
            'preview': preview
        })
    return jsonify(summaries)

@app.route('/api/summary/<name>')
def api_summary(name):
    p = get_pipeline()
    f = p.summaries_dir / f'{name}_summary.md'
    if f.exists():
        return f.read_text(encoding='utf-8'), 200, {'Content-Type': 'text/plain; charset=utf-8'}
    return 'Not found', 404

if __name__ == '__main__':
    print("\n🎙️ Podcast Pipeline Dashboard v5")
    print("=" * 40)
    print("📍 http://localhost:8080")
    print("=" * 40 + "\n")
    
    # 啟動排程線程
    import threading
    scheduler_t = threading.Thread(target=scheduler_thread, daemon=True)
    scheduler_t.start()
    print("📅 排程線程已啟動")
    
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
