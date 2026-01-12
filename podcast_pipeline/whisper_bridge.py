"""
Whisper Bridge - 透過 SMB 與 Windows Whisper 整合

這個模組負責：
1. 將音檔複製到 Windows 的 input 資料夾
2. 監控 output 資料夾等待轉錄結果
3. 讀取繁體中文逐字稿
"""

import shutil
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    """轉錄結果"""
    success: bool
    transcript: Optional[str] = None
    file_path: Optional[Path] = None
    error: Optional[str] = None


class WhisperBridge:
    """Windows Whisper 橋接器（透過 SMB 掛載）"""
    
    def __init__(self, config: dict):
        """
        初始化 Whisper Bridge
        
        Args:
            config: 設定字典，包含 input_dir, output_dir, output_suffix, timeout
        """
        self.input_dir = Path(config['input_dir'])
        self.output_dir = Path(config['output_dir'])
        self.output_suffix = config.get('output_suffix', '_tw.txt')
        self.timeout = config.get('timeout', 7200)  # 預設 2 小時
    
    def is_connected(self) -> bool:
        """檢查 SMB 連接是否正常"""
        return self.input_dir.exists() and self.output_dir.exists()
    
    def submit_audio(self, audio_path: Path, target_filename: Optional[str] = None) -> str:
        """
        將音檔複製到 Windows input 資料夾
        
        Args:
            audio_path: 本地音檔路徑
            target_filename: 目標檔名（可選，預設使用原檔名）
            
        Returns:
            檔案 stem（不含副檔名）
        """
        if not self.is_connected():
            raise ConnectionError("無法連接到 Windows Whisper 資料夾，請確認 SMB 掛載正常")
        
        if not audio_path.exists():
            raise FileNotFoundError(f"找不到音檔：{audio_path}")
        
        # 決定目標檔名
        if target_filename:
            target_name = target_filename if '.' in target_filename else f"{target_filename}{audio_path.suffix}"
        else:
            target_name = audio_path.name
        
        dest = self.input_dir / target_name
        
        # 複製檔案
        print(f"📤 複製音檔到 Windows: {dest.name}")
        shutil.copy2(audio_path, dest)
        
        return dest.stem
    
    def check_transcript_exists(self, file_stem: str) -> bool:
        """檢查轉錄結果是否已存在"""
        expected_output = self.output_dir / f"{file_stem}{self.output_suffix}"
        return expected_output.exists()
    
    def get_transcript(self, file_stem: str) -> Optional[str]:
        """
        讀取轉錄結果（如果存在）
        
        Args:
            file_stem: 檔案 stem（不含副檔名）
            
        Returns:
            逐字稿內容，如果不存在則返回 None
        """
        expected_output = self.output_dir / f"{file_stem}{self.output_suffix}"
        
        if expected_output.exists():
            return expected_output.read_text(encoding='utf-8')
        return None
    
    def wait_for_transcript(
        self, 
        file_stem: str, 
        timeout: Optional[int] = None,
        check_interval: int = 30,
        progress_callback: Optional[callable] = None
    ) -> TranscriptionResult:
        """
        等待並讀取轉錄結果
        
        Args:
            file_stem: 檔案 stem（不含副檔名）
            timeout: 超時時間（秒），預設使用設定檔中的值
            check_interval: 檢查間隔（秒）
            progress_callback: 進度回調函數 callback(elapsed_seconds, status_message)
            
        Returns:
            TranscriptionResult 物件
        """
        timeout = timeout or self.timeout
        expected_output = self.output_dir / f"{file_stem}{self.output_suffix}"
        
        print(f"⏳ 等待 Windows Whisper 轉錄完成：{file_stem}")
        print(f"   預期輸出檔案：{expected_output}")
        
        start = time.time()
        
        while time.time() - start < timeout:
            elapsed = int(time.time() - start)
            
            if expected_output.exists():
                # 等待檔案寫入完成（檔案大小穩定）
                time.sleep(2)
                try:
                    content = expected_output.read_text(encoding='utf-8')
                    print(f"✅ 轉錄完成！耗時 {elapsed} 秒")
                    return TranscriptionResult(
                        success=True,
                        transcript=content,
                        file_path=expected_output
                    )
                except Exception as e:
                    print(f"⚠️ 讀取檔案時發生錯誤：{e}")
            
            # 進度回調
            if progress_callback:
                remaining = timeout - elapsed
                progress_callback(elapsed, f"等待中... ({elapsed}s / {timeout}s)")
            
            time.sleep(check_interval)
        
        print(f"❌ 轉錄超時（{timeout} 秒）")
        return TranscriptionResult(
            success=False,
            error=f"轉錄超時（超過 {timeout} 秒）"
        )
    
    def list_pending_files(self) -> list[str]:
        """列出 input 資料夾中尚未處理的檔案"""
        if not self.is_connected():
            return []
        
        pending = []
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm'}
        
        for f in self.input_dir.iterdir():
            if f.suffix.lower() in audio_extensions:
                # 檢查是否已有對應的輸出檔
                if not self.check_transcript_exists(f.stem):
                    pending.append(f.stem)
        
        return pending
    
    def list_completed_transcripts(self) -> list[Path]:
        """列出所有已完成的轉錄檔案"""
        if not self.is_connected():
            return []
        
        return list(self.output_dir.glob(f"*{self.output_suffix}"))
    
    def cleanup_input(self, file_stem: str) -> bool:
        """
        清理 input 資料夾中已處理的音檔
        
        Args:
            file_stem: 檔案 stem
            
        Returns:
            是否成功刪除
        """
        audio_extensions = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.webm']
        
        for ext in audio_extensions:
            audio_file = self.input_dir / f"{file_stem}{ext}"
            if audio_file.exists():
                try:
                    audio_file.unlink()
                    print(f"🧹 已清理：{audio_file.name}")
                    return True
                except Exception as e:
                    print(f"⚠️ 清理失敗：{e}")
        
        return False


# 測試用
if __name__ == "__main__":
    config = {
        'input_dir': '/Volumes/desktop-0i312mm/Users/PONY/Documents/whisper/whisper.cpp/input',
        'output_dir': '/Volumes/desktop-0i312mm/Users/PONY/Documents/whisper/whisper.cpp/output',
        'output_suffix': '_tw.txt',
        'timeout': 3600
    }
    
    bridge = WhisperBridge(config)
    
    print(f"連接狀態：{'✅ 已連接' if bridge.is_connected() else '❌ 未連接'}")
    
    if bridge.is_connected():
        print(f"\n待處理檔案：{bridge.list_pending_files()}")
        print(f"已完成轉錄：{len(bridge.list_completed_transcripts())} 個")
