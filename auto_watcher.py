#!/usr/bin/env python3
"""
🔄 Podcast 自動監控器 v3.0

功能：
- 掃描 Whisper output 資料夾
- 智慧判斷：缺逐字稿補逐字稿、缺摘要補摘要
- 自動更新 sidebar.json

使用方法：
    # 處理所有逐字稿（缺啥補啥）
    python auto_watcher.py --once
    
    # 持續監控
    python auto_watcher.py
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


# Whisper 檔名前綴對應到節目名稱
PREFIX_TO_PROGRAM = {
    "CFG": "財報狗",
    "MDJ": "Money DJ",
    "GY": "股癌",
    "MM": "M平方",
}

# 無前綴時，根據 EP 編號範圍判斷
def guess_program_from_ep(ep_num: int) -> str:
    """根據 EP 編號猜測節目（當沒有前綴時）"""
    if 290 <= ep_num <= 310:  # M平方
        return "M平方"
    elif 620 <= ep_num <= 640:  # 股癌
        return "股癌"
    elif 580 <= ep_num <= 600:  # 財報狗
        return "財報狗"
    elif 460 <= ep_num <= 470:  # Money DJ
        return "Money DJ"
    return ""


def parse_whisper_filename(filename: str) -> dict:
    """解析 Whisper 逐字稿檔名"""
    stem = filename.replace("_tw.txt", "").replace("_tw", "")
    
    # 嘗試匹配有前綴的格式: CFG_EP585, MDJ_EP460, GY_EP627
    match = re.match(r"^([A-Z]+)_EP(\d+)$", stem)
    if match:
        prefix = match.group(1)
        ep_num = int(match.group(2))
        program = PREFIX_TO_PROGRAM.get(prefix, "")
        return {
            "stem": stem,
            "prefix": prefix,
            "ep_num": ep_num,
            "program": program,
            "canonical_name": f"{program}EP{ep_num}" if program else stem
        }
    
    # 嘗試匹配無前綴的格式: EP296
    match = re.match(r"^EP(\d+)$", stem)
    if match:
        ep_num = int(match.group(1))
        program = guess_program_from_ep(ep_num)
        return {
            "stem": stem,
            "prefix": "",
            "ep_num": ep_num,
            "program": program,
            "canonical_name": f"{program}EP{ep_num}" if program else stem
        }
    
    # 其他格式，直接用原名
    return {
        "stem": stem,
        "prefix": "",
        "ep_num": 0,
        "program": "",
        "canonical_name": stem
    }


def update_sidebar(site_dir: Path, summaries_dir: Path, transcripts_dir: Path):
    """更新 sidebar.json"""
    sidebar_path = site_dir / ".vitepress" / "sidebar.json"
    
    program_names = ["Money DJ", "M平方", "股癌", "財報狗"]
    
    summaries = {p: [] for p in program_names}
    transcripts = {p: [] for p in program_names}
    
    # 掃描摘要
    for f in sorted(summaries_dir.glob("*_summary.md"), reverse=True):
        name = f.stem.replace("_summary", "")
        for prog in program_names:
            if name.startswith(prog.replace(" ", "")):
                ep_match = re.search(r"EP(\d+)", name)
                if ep_match:
                    summaries[prog].append({
                        "text": f"EP{ep_match.group(1)}",
                        "link": f"/summaries/{f.name}"
                    })
                break
    
    # 掃描逐字稿
    for f in sorted(transcripts_dir.glob("*_transcript.md"), reverse=True):
        name = f.stem.replace("_transcript", "")
        for prog in program_names:
            if name.startswith(prog.replace(" ", "")):
                ep_match = re.search(r"EP(\d+)", name)
                if ep_match:
                    transcripts[prog].append({
                        "text": f"EP{ep_match.group(1)}",
                        "link": f"/transcripts/{f.name}"
                    })
                break
    
    sidebar = {
        "/summaries/": [{
            "text": "節目列表",
            "items": [{"text": p, "collapsed": True, "items": summaries[p]} for p in program_names]
        }],
        "/transcripts/": [{
            "text": "逐字稿列表",
            "items": [{"text": p, "collapsed": True, "items": transcripts[p]} for p in program_names]
        }]
    }
    
    sidebar_path.write_text(json.dumps(sidebar, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Podcast 自動監控器 v3.0')
    parser.add_argument('--interval', type=int, default=60, help='監控間隔（秒）')
    parser.add_argument('--template', default='stock_analysis', help='摘要模板')
    parser.add_argument('--once', action='store_true', help='只執行一次')
    args = parser.parse_args()
    
    print("""
╔════════════════════════════════════════════════════════════╗
║           🔄 Podcast 自動監控器 v3.0                        ║
║           (缺啥補啥 智慧版)                                  ║
╚════════════════════════════════════════════════════════════╝
""")
    
    pipeline = PodcastPipeline()
    
    if not pipeline.whisper.is_connected():
        print("❌ 無法連接 Whisper 資料夾！")
        return
    
    summaries_dir = pipeline.summaries_dir
    site_summaries_dir = pipeline.site_summaries_dir
    site_transcripts_dir = pipeline.site_transcripts_dir
    
    print(f"📂 監控目錄：{pipeline.whisper.output_dir}")
    print(f"{'─'*50}")
    
    # 收集現有的摘要和逐字稿（用 canonical_name）
    existing_summaries = set()
    existing_transcripts = set()
    
    for f in summaries_dir.glob("*_summary.md"):
        name = f.stem.replace("_summary", "")
        existing_summaries.add(name)
    
    for f in site_transcripts_dir.glob("*_transcript.md"):
        name = f.stem.replace("_transcript", "")
        existing_transcripts.add(name)
    
    print(f"📝 現有摘要：{len(existing_summaries)} 個")
    print(f"📄 現有逐字稿：{len(existing_transcripts)} 個")
    print(f"{'─'*50}\n")
    
    while True:
        now = datetime.now().strftime('%H:%M:%S')
        
        # 掃描 Whisper output
        whisper_files = list(pipeline.whisper.output_dir.glob('*_tw.txt'))
        
        need_transcript = []
        need_summary = []
        
        for wf in whisper_files:
            info = parse_whisper_filename(wf.name)
            canonical = info["canonical_name"]
            
            # 檢查缺什麼
            has_summary = canonical in existing_summaries
            has_transcript = canonical in existing_transcripts
            
            if not has_transcript:
                need_transcript.append((wf, info))
            if not has_summary:
                need_summary.append((wf, info))
        
        # 統計
        total_tasks = len([x for x in need_transcript if x not in [(nf, ni) for nf, ni in need_summary]]) + len(need_summary)
        
        if need_transcript or need_summary:
            print(f"\n[{now}] 📊 狀態：")
            print(f"   需補逐字稿：{len(need_transcript)} 個")
            print(f"   需補摘要：{len(need_summary)} 個")
        
        # 處理需要補的項目
        processed_count = 0
        
        for wf, info in need_transcript:
            canonical = info["canonical_name"]
            has_summary = canonical in existing_summaries
            
            print(f"\n[{now}] 📄 處理：{wf.name} → {canonical}")
            
            # 讀取逐字稿
            transcript = wf.read_text(encoding='utf-8')
            print(f"   📄 逐字稿長度：{len(transcript)} 字")
            
            if has_summary:
                # 只需要補逐字稿（只跑潤稿）
                print(f"   ✅ 已有摘要，只補潤稿逐字稿...")
                
                polish_result = pipeline.summarizer.polish_transcript(transcript, args.template)
                
                if polish_result.success:
                    polished = polish_result.content
                    transcript_md = pipeline.summarizer.format_transcript_for_display(
                        polished,
                        canonical,
                        info["program"],
                        ""
                    )
                    transcript_path = site_transcripts_dir / f"{canonical}_transcript.md"
                    transcript_path.write_text(transcript_md, encoding='utf-8')
                    existing_transcripts.add(canonical)
                    print(f"   ✅ 逐字稿已儲存：{transcript_path.name}")
                else:
                    print(f"   ❌ 潤稿失敗：{polish_result.error}")
            else:
                # 需要跑完整流程（潤稿 + 摘要）
                print(f"   🤖 完整處理（潤稿 + 摘要）...")
                
                result = pipeline.summarizer.process(
                    transcript=transcript,
                    episode_title=canonical,
                    template_name=args.template
                )
                
                if result.success:
                    # 儲存摘要
                    summary_path = summaries_dir / f"{canonical}_summary.md"
                    summary_path.write_text(result.summary, encoding='utf-8')
                    existing_summaries.add(canonical)
                    
                    # 儲存摘要到 site（含 frontmatter）
                    site_summary = pipeline._add_frontmatter_to_summary(
                        result.summary, canonical, info["program"], "", canonical
                    )
                    site_summary_path = site_summaries_dir / f"{canonical}_summary.md"
                    site_summary_path.write_text(site_summary, encoding='utf-8')
                    
                    # 儲存逐字稿
                    if result.polished_transcript:
                        transcript_md = pipeline.summarizer.format_transcript_for_display(
                            result.polished_transcript,
                            canonical,
                            info["program"],
                            ""
                        )
                        transcript_path = site_transcripts_dir / f"{canonical}_transcript.md"
                        transcript_path.write_text(transcript_md, encoding='utf-8')
                        existing_transcripts.add(canonical)
                        print(f"   ✅ 逐字稿已儲存：{transcript_path.name}")
                    
                    print(f"   ✅ 摘要已儲存：{summary_path.name}")
                else:
                    print(f"   ❌ 處理失敗：{result.error}")
            
            processed_count += 1
        
        if processed_count > 0:
            # 更新 sidebar
            update_sidebar(pipeline.site_dir, site_summaries_dir, site_transcripts_dir)
            print(f"\n   📋 sidebar.json 已更新")
        
        if not need_transcript and not need_summary:
            print(f"[{now}] ✅ 全部完成！沒有缺漏的項目", end='\r')
        
        if args.once:
            print(f"\n\n✅ 單次執行完成！處理了 {processed_count} 個項目")
            break
        
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 監控已停止")
