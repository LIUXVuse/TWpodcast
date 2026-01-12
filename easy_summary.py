#!/usr/bin/env python3
"""
🎙️ Podcast 摘要生成器 - 簡易版

使用方法：
    python easy_summary.py

功能：
    1. 列出 Windows 上已轉錄好的逐字稿
    2. 選擇一個生成摘要
    3. 摘要會存到 data/summaries/ 資料夾
"""

from pathlib import Path
from podcast_pipeline import PodcastPipeline


def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║           🎙️ Podcast 摘要生成器（簡易版）                 ║
╚════════════════════════════════════════════════════════════╝
""")
    
    # 初始化
    pipeline = PodcastPipeline()
    
    # 檢查連接
    if not pipeline.whisper.is_connected():
        print("❌ 無法連接 Windows 電腦！")
        print("   請確認你的 Windows 電腦已開機且有分享資料夾")
        return
    
    # 列出已有的逐字稿
    transcripts = sorted(pipeline.whisper.list_completed_transcripts())
    
    if not transcripts:
        print("⚠️ 還沒有任何逐字稿！")
        print("   請先在 Windows 上執行 Whisper 轉錄")
        return
    
    print(f"📄 找到 {len(transcripts)} 個已轉錄的逐字稿：\n")
    
    # 顯示最近 10 個
    recent = transcripts[-10:]
    for i, t in enumerate(recent, 1):
        print(f"  {i}. {t.name}")
    
    print(f"\n{'─'*50}")
    
    # 選擇檔案
    try:
        choice = input("\n請輸入編號選擇要生成摘要的檔案 (1-10)，或按 Enter 取消：")
        if not choice.strip():
            print("👋 已取消")
            return
        
        idx = int(choice) - 1
        if idx < 0 or idx >= len(recent):
            print("❌ 無效的編號")
            return
        
        selected = recent[idx]
        
    except ValueError:
        print("❌ 請輸入數字")
        return
    
    # 選擇模板
    print(f"\n📋 可用的摘要模板：")
    templates = pipeline.summarizer.get_template_names()
    for i, name in enumerate(templates, 1):
        info = pipeline.summarizer.get_template_info(name)
        print(f"  {i}. {info['name']}")
    
    try:
        t_choice = input("\n請選擇模板 (1-4)，預設 1.股票財經：") or "1"
        t_idx = int(t_choice) - 1
        template = templates[t_idx] if 0 <= t_idx < len(templates) else 'stock_analysis'
    except:
        template = 'stock_analysis'
    
    print(f"\n{'═'*50}")
    print(f"📄 檔案：{selected.name}")
    print(f"📋 模板：{template}")
    print(f"{'═'*50}")
    
    confirm = input("\n確定要生成摘要嗎？(y/n) ") or "y"
    if confirm.lower() != 'y':
        print("👋 已取消")
        return
    
    # 讀取逐字稿
    print("\n📖 讀取逐字稿中...")
    transcript = selected.read_text(encoding='utf-8')
    print(f"   共 {len(transcript)} 字")
    
    # 生成標題
    episode_title = selected.stem.replace('_tw', '')
    
    # 生成摘要
    print("\n🤖 正在用 AI 生成摘要（可能需要 1-2 分鐘）...")
    print("   請耐心等待...\n")
    
    result = pipeline.summarizer.process(
        transcript=transcript,
        episode_title=episode_title,
        template_name=template
    )
    
    if result.success:
        # 儲存摘要
        output_path = pipeline.summaries_dir / f"{episode_title}_summary.md"
        output_path.write_text(result.summary, encoding='utf-8')
        
        print(f"\n{'═'*50}")
        print("✅ 摘要生成成功！")
        print(f"{'═'*50}")
        print(f"\n📁 摘要已儲存到：{output_path}")
        print(f"\n{'─'*50}")
        print("📝 摘要預覽：")
        print(f"{'─'*50}")
        # 顯示前 1000 字
        print(result.summary[:1000])
        if len(result.summary) > 1000:
            print("...")
            print(f"\n（共 {len(result.summary)} 字，完整內容請查看檔案）")
    else:
        print(f"\n❌ 生成失敗：{result.error}")


if __name__ == "__main__":
    main()
