#!/usr/bin/env python3
"""
🔄 Podcast 自動監控器

功能：
- 監控 Whisper output 資料夾
- 當新的逐字稿出現時，自動用 Ollama 生成摘要
- 同時輸出潤稿後的逐字稿到 site/transcripts
- 自動更新 sidebar.json
- 可設定監控間隔和檔名過濾

使用方法：
    # 處理所有逐字稿
    python auto_watcher.py
    
    # 只處理 EP 開頭的（財報狗）
    python auto_watcher.py --prefix EP
    
    # 只處理 S3EP 開頭的（另一個節目）
    python auto_watcher.py --prefix S3EP
    
    # 指定監控間隔（秒）
    python auto_watcher.py --prefix EP --interval 30
"""

import sys
import time
import json
import argparse
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from podcast_pipeline import PodcastPipeline


def update_sidebar(site_dir: Path, summaries_dir: Path, transcripts_dir: Path):
    """更新 sidebar.json"""
    sidebar_path = site_dir / ".vitepress" / "sidebar.json"
    
    # 節目名稱對應
    program_patterns = {
        "Money DJ": r"^Money DJ",
        "M平方": r"^M平方",
        "股癌": r"^股癌",
        "財報狗": r"^財報狗"
    }
    
    # 收集摘要和逐字稿
    summaries = {}
    transcripts = {}
    
    for prog_name in program_patterns:
        summaries[prog_name] = []
        transcripts[prog_name] = []
    
    # 掃描摘要
    for f in sorted(summaries_dir.glob("*_summary.md"), reverse=True):
        for prog_name, pattern in program_patterns.items():
            if re.match(pattern, f.stem.replace("_summary", "")):
                ep_match = re.search(r"EP(\d+)", f.stem)
                if ep_match:
                    summaries[prog_name].append({
                        "text": f"EP{ep_match.group(1)}",
                        "link": f"/summaries/{f.name}"
                    })
                break
    
    # 掃描逐字稿
    for f in sorted(transcripts_dir.glob("*_transcript.md"), reverse=True):
        for prog_name, pattern in program_patterns.items():
            if re.match(pattern, f.stem.replace("_transcript", "")):
                ep_match = re.search(r"EP(\d+)", f.stem)
                if ep_match:
                    transcripts[prog_name].append({
                        "text": f"EP{ep_match.group(1)}",
                        "link": f"/transcripts/{f.name}"
                    })
                break
    
    # 建立 sidebar 結構
    sidebar = {
        "/summaries/": [{
            "text": "節目列表",
            "items": [
                {"text": prog_name, "collapsed": True, "items": summaries.get(prog_name, [])}
                for prog_name in program_patterns.keys()
            ]
        }],
        "/transcripts/": [{
            "text": "逐字稿列表",
            "items": [
                {"text": prog_name, "collapsed": True, "items": transcripts.get(prog_name, [])}
                for prog_name in program_patterns.keys()
            ]
        }]
    }
    
    sidebar_path.write_text(json.dumps(sidebar, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"   📋 sidebar.json 已更新")


def main():
    parser = argparse.ArgumentParser(description='Podcast 自動監控器')
    parser.add_argument('--interval', type=int, default=30, help='監控間隔（秒）')
    parser.add_argument('--template', default='stock_analysis', help='摘要模板')
    parser.add_argument('--once', action='store_true', help='只執行一次（不持續監控）')
    parser.add_argument('--prefix', default='', help='檔名前綴過濾（如 EP 或 S3EP）')
    args = parser.parse_args()
    
    print("""
╔════════════════════════════════════════════════════════════╗
║           🔄 Podcast 自動監控器 v2.0                        ║
║           (含逐字稿輸出與 sidebar 更新)                      ║
╚════════════════════════════════════════════════════════════╝
""")
    
    pipeline = PodcastPipeline()
    
    # 檢查連接
    if not pipeline.whisper.is_connected():
        print("❌ 無法連接 Whisper 資料夾！")
        print(f"   請確認 {pipeline.whisper.output_dir} 已掛載")
        return
    
    print(f"📂 監控目錄：{pipeline.whisper.output_dir}")
    print(f"📋 使用模板：{args.template}")
    print(f"⏱️  監控間隔：{args.interval} 秒")
    if args.prefix:
        print(f"🔍 檔名過濾：只處理 {args.prefix}* 開頭的檔案")
    print(f"{'─'*50}")
    
    # 記錄已處理的檔案
    processed = set()
    summaries_dir = pipeline.summaries_dir
    site_summaries_dir = pipeline.site_summaries_dir
    site_transcripts_dir = pipeline.site_transcripts_dir
    
    # 載入已存在的摘要（避免重複處理）
    for f in summaries_dir.glob('*_summary.md'):
        stem = f.stem.replace('_summary', '')
        processed.add(stem)
    
    print(f"📝 已有 {len(processed)} 個摘要")
    print(f"{'─'*50}\n")
    
    while True:
        now = datetime.now().strftime('%H:%M:%S')
        
        # 掃描 output 資料夾
        transcripts = list(pipeline.whisper.output_dir.glob('*_tw.txt'))
        
        new_count = 0
        for transcript_path in transcripts:
            stem = transcript_path.stem.replace('_tw', '')
            
            # 前綴過濾
            if args.prefix and not stem.startswith(args.prefix):
                continue
            
            if stem in processed:
                continue
            
            new_count += 1
            print(f"\n[{now}] 🆕 發現新逐字稿：{transcript_path.name}")
            
            # 讀取逐字稿
            transcript = transcript_path.read_text(encoding='utf-8')
            print(f"   📄 逐字稿長度：{len(transcript)} 字")
            
            # 生成摘要
            print(f"   🤖 生成摘要中（使用 {args.template} 模板）...")
            
            result = pipeline.summarizer.process(
                transcript=transcript,
                episode_title=stem,
                template_name=args.template
            )
            
            if result.success:
                # 儲存摘要到 data 目錄
                output_path = summaries_dir / f"{stem}_summary.md"
                output_path.write_text(result.summary, encoding='utf-8')
                
                # 從 stem 推斷節目名稱
                podcast_name = ""
                for name in ["Money DJ", "M平方", "股癌", "財報狗"]:
                    if stem.startswith(name.replace(" ", "")):
                        podcast_name = name
                        break
                
                # 儲存摘要到 site 目錄（包含 frontmatter）
                site_summary = pipeline._add_frontmatter_to_summary(
                    result.summary,
                    stem,
                    podcast_name,
                    "",  # 音訊 URL 未知
                    stem
                )
                site_summary_path = site_summaries_dir / f"{stem}_summary.md"
                site_summary_path.write_text(site_summary, encoding='utf-8')
                
                # 儲存潤稿逐字稿
                if result.polished_transcript:
                    transcript_md = pipeline.summarizer.format_transcript_for_display(
                        result.polished_transcript,
                        stem,
                        podcast_name,
                        ""  # 音訊 URL 未知
                    )
                    transcript_path = site_transcripts_dir / f"{stem}_transcript.md"
                    transcript_path.write_text(transcript_md, encoding='utf-8')
                    print(f"   ✅ 逐字稿已儲存：{transcript_path.name}")
                
                # 更新 sidebar
                update_sidebar(pipeline.site_dir, site_summaries_dir, site_transcripts_dir)
                
                print(f"   ✅ 摘要已儲存：{output_path.name}")
                processed.add(stem)
            else:
                print(f"   ❌ 摘要生成失敗：{result.error}")
        
        if new_count == 0:
            print(f"[{now}] 😴 沒有新的逐字稿，等待 {args.interval} 秒...", end='\r')
        
        if args.once:
            print(f"\n\n✅ 單次執行完成！共處理 {new_count} 個新逐字稿")
            break
        
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 監控已停止")

