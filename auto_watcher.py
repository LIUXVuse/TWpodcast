#!/usr/bin/env python3
"""
🔄 Podcast 自動監控器

功能：
- 監控 Whisper output 資料夾
- 當新的逐字稿出現時，自動用 Ollama 生成摘要
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
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from podcast_pipeline import PodcastPipeline


def main():
    parser = argparse.ArgumentParser(description='Podcast 自動監控器')
    parser.add_argument('--interval', type=int, default=30, help='監控間隔（秒）')
    parser.add_argument('--template', default='stock_analysis', help='摘要模板')
    parser.add_argument('--once', action='store_true', help='只執行一次（不持續監控）')
    parser.add_argument('--prefix', default='', help='檔名前綴過濾（如 EP 或 S3EP）')
    args = parser.parse_args()
    
    print("""
╔════════════════════════════════════════════════════════════╗
║           🔄 Podcast 自動監控器                             ║
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
                # 儲存摘要
                output_path = summaries_dir / f"{stem}_summary.md"
                output_path.write_text(result.summary, encoding='utf-8')
                
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
