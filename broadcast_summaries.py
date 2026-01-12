"""
批次發送摘要到 Telegram 頻道
"""

import sys
from pathlib import Path

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent))
from podcast_pipeline.telegram_notifier import TelegramNotifier
import yaml
import time

def load_config():
    config_file = Path(__file__).parent / 'config' / 'services.yaml'
    with open(config_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('telegram', {})

def main():
    config = load_config()
    notifier = TelegramNotifier(config)
    
    if not notifier.is_configured():
        print("❌ Telegram 未設定")
        return
    
    summaries_dir = Path(__file__).parent / 'data' / 'summaries'
    summaries = sorted(summaries_dir.glob('*_summary.md'))
    
    print(f"📂 找到 {len(summaries)} 個摘要")
    print()
    
    for i, summary in enumerate(summaries, 1):
        print(f"[{i}/{len(summaries)}] 📤 發送：{summary.name}")
        
        result = notifier.send_summary(summary)
        
        if result.success:
            print(f"         ✅ 成功")
        else:
            print(f"         ❌ 失敗：{result.error}")
        
        # 避免 Telegram 限流
        if i < len(summaries):
            time.sleep(3)
    
    print()
    print("🎉 批次發送完成！")

if __name__ == "__main__":
    main()
