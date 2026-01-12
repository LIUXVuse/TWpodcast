"""
Feed Tracker - RSS 追蹤器

負責：
1. 追蹤多個 RSS Feed
2. 偵測新集數
3. 記錄已處理的集數
"""

import yaml
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass
import sys

# 加入父目錄以便匯入 rss_downloader
sys.path.insert(0, str(Path(__file__).parent.parent))
from rss_downloader.parser import parse_rss, PodcastInfo, Episode


@dataclass
class FeedConfig:
    """Feed 設定"""
    name: str
    url: str
    enabled: bool
    filename_pattern: str
    download_path: str
    template: str


@dataclass
class NewEpisode:
    """新集數資訊"""
    feed_name: str
    episode: Episode
    filename: str
    download_path: Path


class FeedTracker:
    """RSS Feed 追蹤器"""
    
    def __init__(self, config_path: Optional[Path] = None, db_path: Optional[Path] = None):
        """
        初始化 Feed Tracker
        
        Args:
            config_path: feeds.yaml 路徑
            db_path: SQLite 資料庫路徑
        """
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "feeds.yaml"
        self.db_path = db_path or Path(__file__).parent.parent / "data" / "tracking.db"
        
        # 確保資料目錄存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化資料庫
        self._init_db()
        
        # 載入設定
        self.feeds = self._load_feeds()
    
    def _init_db(self):
        """初始化 SQLite 資料庫"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_name TEXT NOT NULL,
                episode_index INTEGER NOT NULL,
                episode_title TEXT,
                audio_url TEXT,
                filename TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'downloaded',
                transcript_path TEXT,
                summary_path TEXT,
                UNIQUE(feed_name, episode_index)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feed_last_check (
                feed_name TEXT PRIMARY KEY,
                last_checked TIMESTAMP,
                last_episode_index INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_feeds(self) -> List[FeedConfig]:
        """載入 Feed 設定"""
        if not self.config_path.exists():
            return []
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        feeds = []
        for feed_data in data.get('feeds', []):
            if feed_data.get('enabled', True):
                feeds.append(FeedConfig(
                    name=feed_data['name'],
                    url=feed_data['url'],
                    enabled=feed_data.get('enabled', True),
                    filename_pattern=feed_data.get('filename_pattern', 'EP{index:03d}'),
                    download_path=Path(feed_data.get('download_path', '~/Downloads/Podcasts')).expanduser(),
                    template=feed_data.get('template', 'default')
                ))
        
        return feeds
    
    def reload_config(self):
        """重新載入設定"""
        self.feeds = self._load_feeds()
    
    def get_feed_names(self) -> List[str]:
        """取得所有 Feed 名稱"""
        return [f.name for f in self.feeds]
    
    def is_episode_processed(self, feed_name: str, episode_index: int) -> bool:
        """檢查集數是否已處理"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT 1 FROM processed_episodes WHERE feed_name = ? AND episode_index = ?',
            (feed_name, episode_index)
        )
        
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def mark_episode_processed(
        self,
        feed_name: str,
        episode: Episode,
        filename: str,
        status: str = 'downloaded'
    ):
        """標記集數為已處理"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO processed_episodes 
            (feed_name, episode_index, episode_title, audio_url, filename, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (feed_name, episode.index, episode.title, episode.audio_url, filename, status))
        
        conn.commit()
        conn.close()
    
    def update_episode_status(
        self,
        feed_name: str,
        episode_index: int,
        status: str,
        transcript_path: Optional[str] = None,
        summary_path: Optional[str] = None
    ):
        """更新集數狀態"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if transcript_path:
            cursor.execute('''
                UPDATE processed_episodes 
                SET status = ?, transcript_path = ?
                WHERE feed_name = ? AND episode_index = ?
            ''', (status, transcript_path, feed_name, episode_index))
        elif summary_path:
            cursor.execute('''
                UPDATE processed_episodes 
                SET status = ?, summary_path = ?
                WHERE feed_name = ? AND episode_index = ?
            ''', (status, summary_path, feed_name, episode_index))
        else:
            cursor.execute('''
                UPDATE processed_episodes 
                SET status = ?
                WHERE feed_name = ? AND episode_index = ?
            ''', (status, feed_name, episode_index))
        
        conn.commit()
        conn.close()
    
    def check_new_episodes(self, feed_name: Optional[str] = None) -> List[NewEpisode]:
        """
        檢查新集數
        
        Args:
            feed_name: 指定 Feed 名稱，None 表示檢查所有 Feed
            
        Returns:
            新集數列表
        """
        feeds_to_check = self.feeds
        if feed_name:
            feeds_to_check = [f for f in self.feeds if f.name == feed_name]
        
        new_episodes = []
        
        for feed in feeds_to_check:
            print(f"📡 檢查 {feed.name}...")
            
            try:
                info = parse_rss(feed.url)
                print(f"   找到 {len(info.episodes)} 集")
                
                for episode in info.episodes:
                    if not self.is_episode_processed(feed.name, episode.index):
                        # 生成檔名
                        filename = feed.filename_pattern.format(index=episode.index)
                        if not filename.endswith('.mp3'):
                            filename += '.mp3'
                        
                        new_episodes.append(NewEpisode(
                            feed_name=feed.name,
                            episode=episode,
                            filename=filename,
                            download_path=feed.download_path
                        ))
                
                # 更新最後檢查時間
                self._update_last_check(feed.name, len(info.episodes))
                
            except Exception as e:
                print(f"   ❌ 錯誤：{e}")
        
        print(f"\n🆕 發現 {len(new_episodes)} 個新集數")
        return new_episodes
    
    def _update_last_check(self, feed_name: str, last_episode_index: int):
        """更新最後檢查時間"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO feed_last_check (feed_name, last_checked, last_episode_index)
            VALUES (?, ?, ?)
        ''', (feed_name, datetime.now().isoformat(), last_episode_index))
        
        conn.commit()
        conn.close()
    
    def get_processed_episodes(self, feed_name: Optional[str] = None, limit: int = 50) -> List[dict]:
        """
        取得已處理的集數列表
        
        Args:
            feed_name: Feed 名稱（可選）
            limit: 返回數量限制
            
        Returns:
            已處理集數列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if feed_name:
            cursor.execute('''
                SELECT * FROM processed_episodes 
                WHERE feed_name = ?
                ORDER BY episode_index DESC
                LIMIT ?
            ''', (feed_name, limit))
        else:
            cursor.execute('''
                SELECT * FROM processed_episodes 
                ORDER BY processed_at DESC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_statistics(self) -> dict:
        """取得統計資訊"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 各狀態數量
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM processed_episodes
            GROUP BY status
        ''')
        status_counts = dict(cursor.fetchall())
        
        # 各 Feed 數量
        cursor.execute('''
            SELECT feed_name, COUNT(*) as count
            FROM processed_episodes
            GROUP BY feed_name
        ''')
        feed_counts = dict(cursor.fetchall())
        
        # 總數
        cursor.execute('SELECT COUNT(*) FROM processed_episodes')
        total = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_processed': total,
            'by_status': status_counts,
            'by_feed': feed_counts
        }


# 測試用
if __name__ == "__main__":
    tracker = FeedTracker()
    
    print("📊 Feed Tracker 測試")
    print(f"\n已設定的 Feed：{tracker.get_feed_names()}")
    
    print("\n檢查新集數...")
    new_eps = tracker.check_new_episodes()
    
    for ep in new_eps[:5]:
        print(f"  - [{ep.feed_name}] EP{ep.episode.index}: {ep.episode.title[:40]}...")
    
    print(f"\n統計：{tracker.get_statistics()}")
