#!/usr/bin/env python3
"""
Podcast Pipeline 測試腳本

用於測試各個模組的功能：
1. Whisper 連接
2. Ollama 連接
3. 摘要生成
4. 完整流程
"""

import sys
from pathlib import Path

# 確保可以匯入模組
sys.path.insert(0, str(Path(__file__).parent))

from podcast_pipeline import PodcastPipeline


def test_status():
    """測試系統狀態"""
    print("\n" + "="*60)
    print("📊 測試 1：系統狀態")
    print("="*60)
    
    pipeline = PodcastPipeline()
    status = pipeline.get_status()
    
    print(f"""
📂 Whisper 連接：{'✅ 已連接' if status['whisper']['connected'] else '❌ 未連接'}
   Input: {status['whisper']['input_dir']}
   Output: {status['whisper']['output_dir']}

🤖 Ollama 狀態：
   本地主要 (Windows)：{'✅' if status['ollama']['local']['primary']['connected'] else '❌ 未連接'}
   本地備用 (Mac)：{'✅' if status['ollama']['local']['fallback']['connected'] else '❌ 未連接'}
   預設模型：{status['ollama']['local']['default_model']}

📡 追蹤的 Feed：{status['feeds']}
📋 可用模板：{status['templates']}
📊 已處理集數：{status['statistics']['total_processed']}
""")
    
    return status


def test_ollama():
    """測試 Ollama 生成"""
    print("\n" + "="*60)
    print("🤖 測試 2：Ollama 文字生成")
    print("="*60)
    
    pipeline = PodcastPipeline()
    
    # 簡單測試
    test_prompt = "請用一句話介紹台積電（TSMC）這家公司。"
    print(f"\n測試 Prompt：{test_prompt}")
    print("\n生成中...")
    
    result = pipeline.ollama.generate(test_prompt, timeout=60)
    
    if result.success:
        print(f"\n✅ 成功！使用模型：{result.model}")
        print(f"回應：{result.content[:300]}...")
    else:
        print(f"\n❌ 失敗：{result.error}")
    
    return result.success


def test_summarizer():
    """測試摘要生成"""
    print("\n" + "="*60)
    print("📝 測試 3：摘要模板")
    print("="*60)
    
    pipeline = PodcastPipeline()
    
    print("\n可用模板：")
    for name in pipeline.summarizer.get_template_names():
        info = pipeline.summarizer.get_template_info(name)
        print(f"  - {name}: {info['name']} - {info['description']}")
    
    return True


def test_existing_transcript():
    """測試現有逐字稿的摘要生成"""
    print("\n" + "="*60)
    print("📄 測試 4：處理現有逐字稿")
    print("="*60)
    
    pipeline = PodcastPipeline()
    
    # 檢查是否有現有的逐字稿
    transcripts = list(pipeline.whisper.list_completed_transcripts())
    
    if not transcripts:
        print("\n⚠️ 沒有找到已完成的逐字稿")
        return False
    
    print(f"\n找到 {len(transcripts)} 個逐字稿")
    
    # 取最新的一個測試
    latest = transcripts[-1]
    print(f"測試檔案：{latest.name}")
    
    # 讀取前 500 字做測試
    content = latest.read_text(encoding='utf-8')[:500]
    print(f"內容預覽：{content[:200]}...")
    
    # 詢問是否要生成完整摘要（這會花較長時間）
    print("\n⏭️ 跳過完整摘要生成（需要較長時間）")
    print("   如需測試，請使用：")
    print("   pipeline.process_existing_transcript(transcript_path, '測試標題')")
    
    return True


def check_new_episodes():
    """檢查新集數"""
    print("\n" + "="*60)
    print("📡 測試 5：檢查新集數")
    print("="*60)
    
    pipeline = PodcastPipeline()
    
    print("\n正在檢查 RSS Feed...")
    new_episodes = pipeline.check_new_episodes()
    
    if new_episodes:
        print(f"\n🆕 發現 {len(new_episodes)} 個新集數：")
        for ep in new_episodes[:5]:
            print(f"  - [{ep.feed_name}] EP{ep.episode.index}: {ep.episode.title[:40]}...")
    else:
        print("\n✅ 沒有新集數")
    
    return len(new_episodes)


def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║           🎙️ Podcast Pipeline 測試腳本                     ║
╚════════════════════════════════════════════════════════════╝
""")
    
    # 測試 1：狀態
    status = test_status()
    
    # 測試 2：Ollama
    if status['ollama']['local']['fallback']['connected']:
        test_ollama()
    else:
        print("\n⏭️ 跳過 Ollama 測試（未連接）")
    
    # 測試 3：模板
    test_summarizer()
    
    # 測試 4：現有逐字稿
    if status['whisper']['connected']:
        test_existing_transcript()
    else:
        print("\n⏭️ 跳過逐字稿測試（Whisper 未連接）")
    
    # 測試 5：新集數
    check_new_episodes()
    
    print("\n" + "="*60)
    print("✅ 測試完成！")
    print("="*60)
    print("""
下一步：
1. 確認 Windows IP 並更新 config/services.yaml
2. 在 Windows 上執行 Whisper bat
3. 使用 pipeline.process_episode() 處理新集數
""")


if __name__ == "__main__":
    main()
