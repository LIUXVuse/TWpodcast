#!/usr/bin/env python3
"""
為摘要檔案補上 audioUrl frontmatter

從 RSS feed 取得音訊 URL，更新現有摘要和逐字稿的 frontmatter
"""

import sys
import re
import yaml
import feedparser
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))


def load_feeds():
    """載入 feeds 設定"""
    config_path = Path(__file__).parent / "config" / "feeds.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('feeds', [])


def get_audio_urls_from_feed(feed_url: str) -> dict:
    """從 RSS feed 取得所有集數的音訊 URL"""
    audio_urls = {}
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            # 取得集數編號
            title = entry.get('title', '')
            ep_match = re.search(r'EP\.?(\d+)|[Ee][Pp]\.?(\d+)|第(\d+)[集期]', title)
            if ep_match:
                ep_num = ep_match.group(1) or ep_match.group(2) or ep_match.group(3)
            else:
                # 嘗試從 itunes:episode 取得
                ep_num = entry.get('itunes_episode', '')
            
            if not ep_num:
                continue
            
            # 取得音訊 URL
            audio_url = ''
            for link in entry.get('links', []):
                if link.get('type', '').startswith('audio'):
                    audio_url = link.get('href', '')
                    break
            
            if not audio_url and entry.get('enclosures'):
                for enc in entry.enclosures:
                    if enc.get('type', '').startswith('audio'):
                        audio_url = enc.get('href', '')
                        break
            
            if audio_url:
                audio_urls[int(ep_num)] = audio_url
                
    except Exception as e:
        print(f"   ❌ 讀取 feed 失敗：{e}")
    
    return audio_urls


def update_frontmatter(file_path: Path, audio_url: str, podcast_name: str):
    """更新檔案的 frontmatter"""
    content = file_path.read_text(encoding='utf-8')
    
    # 檢查是否已有 frontmatter
    if content.startswith('---'):
        # 找到結束的 ---
        end_idx = content.find('---', 3)
        if end_idx != -1:
            frontmatter_str = content[3:end_idx].strip()
            try:
                frontmatter = yaml.safe_load(frontmatter_str) or {}
            except:
                frontmatter = {}
            body = content[end_idx+3:].lstrip()
        else:
            frontmatter = {}
            body = content
    else:
        frontmatter = {}
        body = content
    
    # 更新 frontmatter
    if not frontmatter.get('audioUrl'):
        frontmatter['audioUrl'] = audio_url
    if not frontmatter.get('podcast'):
        frontmatter['podcast'] = podcast_name
    
    # 重建檔案
    new_content = "---\n"
    new_content += yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
    new_content += "---\n\n"
    new_content += body
    
    file_path.write_text(new_content, encoding='utf-8')


def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║           🔗 補上 Audio URL 到 Frontmatter                  ║
╚════════════════════════════════════════════════════════════╝
""")
    
    site_dir = Path(__file__).parent / "site"
    summaries_dir = site_dir / "summaries"
    transcripts_dir = site_dir / "transcripts"
    
    feeds = load_feeds()
    
    # 建立節目名稱到 audio URLs 的對應
    program_audio_urls = {}
    
    for feed in feeds:
        if not feed.get('enabled', True):
            continue
        
        name = feed['name']
        url = feed['url']
        
        print(f"📡 讀取 {name} 的 RSS feed...")
        audio_urls = get_audio_urls_from_feed(url)
        program_audio_urls[name] = audio_urls
        print(f"   找到 {len(audio_urls)} 個集數的音訊 URL")
    
    print(f"\n{'─'*50}")
    print("📄 更新摘要檔案...")
    
    updated_count = 0
    
    for f in summaries_dir.glob("*_summary.md"):
        name = f.stem.replace("_summary", "")
        
        # 解析節目名稱和集數
        for prog_name in program_audio_urls.keys():
            prog_key = prog_name.replace(" ", "")
            if name.startswith(prog_key):
                ep_match = re.search(r"EP(\d+)", name)
                if ep_match:
                    ep_num = int(ep_match.group(1))
                    audio_url = program_audio_urls[prog_name].get(ep_num, "")
                    if audio_url:
                        update_frontmatter(f, audio_url, prog_name)
                        updated_count += 1
                        print(f"   ✅ {f.name}")
                break
    
    print(f"\n📝 更新逐字稿檔案...")
    
    for f in transcripts_dir.glob("*_transcript.md"):
        if f.name == "index.md":
            continue
        name = f.stem.replace("_transcript", "")
        
        for prog_name in program_audio_urls.keys():
            prog_key = prog_name.replace(" ", "")
            if name.startswith(prog_key):
                ep_match = re.search(r"EP(\d+)", name)
                if ep_match:
                    ep_num = int(ep_match.group(1))
                    audio_url = program_audio_urls[prog_name].get(ep_num, "")
                    if audio_url:
                        update_frontmatter(f, audio_url, prog_name)
                        updated_count += 1
                        print(f"   ✅ {f.name}")
                break
    
    print(f"\n{'─'*50}")
    print(f"✅ 完成！共更新 {updated_count} 個檔案")


if __name__ == "__main__":
    main()
