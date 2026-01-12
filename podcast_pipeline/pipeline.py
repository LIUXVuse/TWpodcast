"""
Podcast Pipeline - 完整流程管理器

整合所有模組，提供一條龍自動化處理：
RSS 追蹤 → 下載 → Whisper 轉錄 → Ollama 潤稿 → 摘要生成 → 輸出
"""

import yaml
import shutil
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import sys

# 加入父目錄
sys.path.insert(0, str(Path(__file__).parent.parent))

from .whisper_bridge import WhisperBridge, TranscriptionResult
from .ollama_client import OllamaClient
from .summarizer import Summarizer, SummaryResult
from .feed_tracker import FeedTracker, NewEpisode
from rss_downloader.downloader import download_episode


@dataclass
class PipelineResult:
    """Pipeline 處理結果"""
    success: bool
    episode_title: str
    feed_name: str
    stages_completed: List[str]
    audio_path: Optional[Path] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    summary_path: Optional[Path] = None
    error: Optional[str] = None


class PodcastPipeline:
    """Podcast 一條龍處理器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化 Pipeline
        
        Args:
            config_path: 設定檔目錄路徑
        """
        self.config_dir = config_path or Path(__file__).parent.parent / "config"
        self.data_dir = Path(__file__).parent.parent / "data"
        
        # 載入設定
        self.services_config = self._load_config("services.yaml")
        
        # 初始化各模組
        self.whisper = WhisperBridge(self.services_config.get('whisper', {}))
        self.ollama = OllamaClient(self.services_config.get('ollama', {}))
        self.summarizer = Summarizer(self.ollama, self.config_dir / "templates.yaml")
        self.tracker = FeedTracker(self.config_dir / "feeds.yaml", self.data_dir / "tracking.db")
        
        # 摘要輸出目錄
        self.summaries_dir = self.data_dir / "summaries"
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, filename: str) -> dict:
        """載入設定檔"""
        config_path = self.config_dir / filename
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def get_status(self) -> dict:
        """取得各模組狀態"""
        return {
            'whisper': {
                'connected': self.whisper.is_connected(),
                'input_dir': str(self.whisper.input_dir),
                'output_dir': str(self.whisper.output_dir)
            },
            'ollama': self.ollama.get_status(),
            'feeds': self.tracker.get_feed_names(),
            'templates': self.summarizer.get_template_names(),
            'statistics': self.tracker.get_statistics()
        }
    
    def check_new_episodes(self, feed_name: Optional[str] = None) -> List[NewEpisode]:
        """檢查新集數"""
        return self.tracker.check_new_episodes(feed_name)
    
    def download_episode(self, new_episode: NewEpisode) -> Optional[Path]:
        """
        下載集數
        
        Args:
            new_episode: 新集數資訊
            
        Returns:
            下載的檔案路徑，失敗返回 None
        """
        try:
            # 確保目錄存在
            new_episode.download_path.mkdir(parents=True, exist_ok=True)
            
            output_path = new_episode.download_path / new_episode.filename
            
            print(f"📥 下載中：{new_episode.episode.title[:50]}...")
            
            # 使用現有的下載功能
            download_episode(
                url=new_episode.episode.audio_url,
                output_path=output_path
            )
            
            if output_path.exists():
                print(f"✅ 下載完成：{output_path.name}")
                
                # 標記為已下載
                self.tracker.mark_episode_processed(
                    new_episode.feed_name,
                    new_episode.episode,
                    new_episode.filename,
                    status='downloaded'
                )
                
                return output_path
            
        except Exception as e:
            print(f"❌ 下載失敗：{e}")
        
        return None
    
    def submit_to_whisper(self, audio_path: Path, target_filename: Optional[str] = None) -> str:
        """
        提交音檔到 Whisper 處理
        
        Args:
            audio_path: 音檔路徑
            target_filename: 目標檔名（用於 Whisper 識別）
            
        Returns:
            檔案 stem
        """
        return self.whisper.submit_audio(audio_path, target_filename)
    
    def wait_for_transcript(self, file_stem: str) -> TranscriptionResult:
        """等待 Whisper 轉錄完成"""
        return self.whisper.wait_for_transcript(file_stem)
    
    def generate_summary(
        self,
        transcript: str,
        episode_title: str,
        template_name: str = 'stock_analysis'
    ) -> SummaryResult:
        """生成摘要"""
        return self.summarizer.process(transcript, episode_title, template_name)
    
    def process_episode(
        self,
        new_episode: NewEpisode,
        template_name: Optional[str] = None,
        wait_for_whisper: bool = True,
        auto_cleanup: bool = False
    ) -> PipelineResult:
        """
        處理單一集數的完整流程
        
        Args:
            new_episode: 新集數資訊
            template_name: 摘要模板名稱
            wait_for_whisper: 是否等待 Whisper 完成
            auto_cleanup: 是否自動清理 input 資料夾
            
        Returns:
            PipelineResult 物件
        """
        stages_completed = []
        template = template_name or self._get_feed_template(new_episode.feed_name)
        
        result = PipelineResult(
            success=False,
            episode_title=new_episode.episode.title,
            feed_name=new_episode.feed_name,
            stages_completed=stages_completed
        )
        
        print(f"\n{'='*60}")
        print(f"🎙️ 開始處理：{new_episode.episode.title}")
        print(f"{'='*60}")
        
        # 步驟 1：下載
        print("\n📥 步驟 1/4：下載音檔")
        audio_path = self.download_episode(new_episode)
        if not audio_path:
            result.error = "下載失敗"
            return result
        
        result.audio_path = audio_path
        stages_completed.append('download')
        
        # 步驟 2：提交 Whisper
        print("\n🎙️ 步驟 2/4：提交 Whisper 轉錄")
        if not self.whisper.is_connected():
            result.error = "無法連接 Windows Whisper（SMB 未掛載）"
            return result
        
        try:
            file_stem = self.submit_to_whisper(audio_path, new_episode.filename)
            stages_completed.append('whisper_submitted')
            
            self.tracker.update_episode_status(
                new_episode.feed_name,
                new_episode.episode.index,
                'whisper_pending'
            )
            
        except Exception as e:
            result.error = f"提交 Whisper 失敗：{e}"
            return result
        
        # 步驟 3：等待轉錄（可選）
        if wait_for_whisper:
            print("\n⏳ 步驟 3/4：等待 Whisper 轉錄完成")
            print("   （請確認 Windows 電腦上的 bat 已執行）")
            
            transcript_result = self.wait_for_transcript(file_stem)
            
            if not transcript_result.success:
                result.error = f"Whisper 轉錄失敗：{transcript_result.error}"
                return result
            
            result.transcript = transcript_result.transcript
            stages_completed.append('whisper_completed')
            
            self.tracker.update_episode_status(
                new_episode.feed_name,
                new_episode.episode.index,
                'transcribed',
                transcript_path=str(transcript_result.file_path)
            )
            
            # 步驟 4：生成摘要
            print("\n📝 步驟 4/4：生成摘要")
            summary_result = self.generate_summary(
                transcript_result.transcript,
                new_episode.episode.title,
                template
            )
            
            if summary_result.success:
                result.summary = summary_result.summary
                stages_completed.append('summary_generated')
                
                # 儲存摘要
                summary_filename = f"{file_stem}_summary.md"
                summary_path = self.summaries_dir / summary_filename
                summary_path.write_text(summary_result.summary, encoding='utf-8')
                result.summary_path = summary_path
                
                self.tracker.update_episode_status(
                    new_episode.feed_name,
                    new_episode.episode.index,
                    'completed',
                    summary_path=str(summary_path)
                )
                
                print(f"\n✅ 摘要已儲存：{summary_path}")
            else:
                result.error = summary_result.error
                return result
        
        # 清理（可選）
        if auto_cleanup:
            self.whisper.cleanup_input(file_stem)
        
        result.success = True
        print(f"\n🎉 處理完成！")
        return result
    
    def _get_feed_template(self, feed_name: str) -> str:
        """取得 Feed 對應的模板"""
        for feed in self.tracker.feeds:
            if feed.name == feed_name:
                return feed.template
        return 'stock_analysis'  # 預設
    
    def process_all_new(
        self,
        template_name: Optional[str] = None,
        max_episodes: int = 10,
        wait_for_whisper: bool = False
    ) -> List[PipelineResult]:
        """
        處理所有新集數
        
        Args:
            template_name: 指定模板（覆蓋 Feed 設定）
            max_episodes: 最多處理幾集
            wait_for_whisper: 是否等待 Whisper
            
        Returns:
            處理結果列表
        """
        new_episodes = self.check_new_episodes()
        
        if not new_episodes:
            print("沒有新集數需要處理")
            return []
        
        results = []
        for i, ep in enumerate(new_episodes[:max_episodes]):
            print(f"\n[{i+1}/{min(len(new_episodes), max_episodes)}]")
            result = self.process_episode(ep, template_name, wait_for_whisper)
            results.append(result)
        
        return results
    
    def process_existing_transcript(
        self,
        transcript_path: Path,
        episode_title: str,
        template_name: str = 'stock_analysis'
    ) -> SummaryResult:
        """
        處理已存在的逐字稿（跳過下載和 Whisper）
        
        Args:
            transcript_path: 逐字稿檔案路徑
            episode_title: 集數標題
            template_name: 模板名稱
            
        Returns:
            SummaryResult 物件
        """
        transcript = transcript_path.read_text(encoding='utf-8')
        return self.generate_summary(transcript, episode_title, template_name)


# 測試用
if __name__ == "__main__":
    pipeline = PodcastPipeline()
    
    print("🎙️ Podcast Pipeline 狀態")
    print("="*50)
    
    status = pipeline.get_status()
    
    print(f"\n📂 Whisper 連接：{'✅' if status['whisper']['connected'] else '❌'}")
    print(f"   Input: {status['whisper']['input_dir']}")
    print(f"   Output: {status['whisper']['output_dir']}")
    
    print(f"\n🤖 Ollama 狀態：")
    ollama_status = status['ollama']
    print(f"   本地主要：{'✅' if ollama_status['local']['primary']['connected'] else '❌'}")
    print(f"   本地備用：{'✅' if ollama_status['local']['fallback']['connected'] else '❌'}")
    
    print(f"\n📡 追蹤的 Feed：{status['feeds']}")
    print(f"📋 可用模板：{status['templates']}")
    print(f"📊 統計：{status['statistics']}")
