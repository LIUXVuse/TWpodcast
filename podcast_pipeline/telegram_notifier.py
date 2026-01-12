"""
Telegram Notifier - 摘要推送到 Telegram

功能：
1. 發送新摘要通知
2. 支援 Markdown 格式
3. 自動截斷過長訊息
"""

import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class TelegramResult:
    """發送結果"""
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None


class TelegramNotifier:
    """Telegram 通知器"""
    
    def __init__(self, config: dict):
        """
        初始化 Telegram 通知器
        
        Args:
            config: 包含 bot_token 和 chat_id 的設定
        """
        self.enabled = config.get('enabled', False)
        self.bot_token = config.get('bot_token', '')
        self.chat_id = config.get('chat_id', '')
        self.max_length = 4000  # Telegram 訊息長度限制約 4096
    
    def is_configured(self) -> bool:
        """檢查是否已設定"""
        return bool(self.enabled and self.bot_token and self.chat_id)
    
    def send_message(
        self, 
        text: str, 
        parse_mode: str = 'Markdown',
        disable_preview: bool = True
    ) -> TelegramResult:
        """
        發送訊息
        
        Args:
            text: 訊息內容
            parse_mode: 解析模式（Markdown 或 HTML）
            disable_preview: 是否禁用連結預覽
            
        Returns:
            TelegramResult
        """
        if not self.is_configured():
            return TelegramResult(success=False, error="Telegram 未設定")
        
        # 截斷過長訊息
        if len(text) > self.max_length:
            text = text[:self.max_length] + "\n\n⚠️ *（訊息過長，已截斷）*"
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        try:
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'disable_web_page_preview': disable_preview
            }
            # 只有在指定 parse_mode 時才加入
            if parse_mode:
                payload['parse_mode'] = parse_mode
            
            resp = requests.post(url, json=payload, timeout=30)
            
            if resp.ok:
                data = resp.json()
                if data.get('ok'):
                    return TelegramResult(
                        success=True,
                        message_id=data['result']['message_id']
                    )
                else:
                    return TelegramResult(
                        success=False,
                        error=data.get('description', '未知錯誤')
                    )
            else:
                return TelegramResult(
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except requests.Timeout:
            return TelegramResult(success=False, error="請求超時")
        except requests.RequestException as e:
            return TelegramResult(success=False, error=str(e))
    
    def send_summary(self, summary_path: Path) -> TelegramResult:
        """
        發送摘要檔案
        
        Args:
            summary_path: 摘要檔案路徑
            
        Returns:
            TelegramResult
        """
        if not summary_path.exists():
            return TelegramResult(success=False, error=f"檔案不存在：{summary_path}")
        
        content = summary_path.read_text(encoding='utf-8')
        
        # 提取標題（第一行 # 開頭）
        lines = content.split('\n')
        title = next((l.replace('# ', '') for l in lines if l.startswith('# ')), summary_path.stem)
        
        # 發送訊息前加上 emoji
        message = f"🎙️ *新摘要上線*\n\n{content}"
        
        # 先嘗試 Markdown 模式
        result = self.send_message(message, parse_mode='Markdown')
        
        # 如果 Markdown 解析失敗，改用純文字模式
        if not result.success and 'parse entities' in str(result.error).lower():
            print(f"⚠️ Markdown 解析失敗，改用純文字模式")
            # 移除 Markdown 格式符號
            plain_message = f"🎙️ 新摘要上線\n\n{content}"
            result = self.send_message(plain_message, parse_mode=None)
        
        if result.success:
            print(f"📱 Telegram 推送成功：{title}")
        else:
            print(f"❌ Telegram 推送失敗：{result.error}")
        
        return result
    
    def send_notification(self, title: str, summary_preview: str = "") -> TelegramResult:
        """
        發送簡短通知
        
        Args:
            title: 通知標題
            summary_preview: 摘要預覽（可選）
        """
        message = f"🎙️ *{title}*"
        if summary_preview:
            message += f"\n\n{summary_preview[:500]}"
        
        return self.send_message(message)
    
    def test_connection(self) -> TelegramResult:
        """測試連接"""
        return self.send_message("🔔 *測試訊息*\n\nPodcast Pipeline 連接成功！")


# 測試用
if __name__ == "__main__":
    config = {
        'enabled': True,
        'bot_token': 'YOUR_BOT_TOKEN',
        'chat_id': 'YOUR_CHAT_ID'
    }
    
    notifier = TelegramNotifier(config)
    
    if notifier.is_configured():
        result = notifier.test_connection()
        print(f"測試結果：{'成功' if result.success else f'失敗 - {result.error}'}")
    else:
        print("請先設定 bot_token 和 chat_id")
