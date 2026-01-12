"""
RSS 解析模組
從 RSS Feed URL 解析 Podcast 集數資訊
"""

import feedparser
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Episode:
    """代表一集 Podcast 的資料結構"""
    index: int           # 集數編號（從 1 開始）
    title: str           # 集數標題
    published: datetime  # 發布日期
    audio_url: str       # 音檔下載連結
    duration: str        # 時長（如果有的話）
    file_size: int       # 檔案大小（bytes）
    
    def get_filename(self) -> str:
        """產生下載時使用的檔案名稱"""
        # 清理標題中不能用於檔名的字元
        safe_title = "".join(c for c in self.title if c not in r'\/:*?"<>|')
        safe_title = safe_title[:80]  # 限制長度
        return f"EP{self.index:03d}_{safe_title}.mp3"


@dataclass
class PodcastInfo:
    """Podcast 頻道資訊"""
    title: str
    description: str
    image_url: Optional[str]
    episodes: List[Episode]


def parse_time_struct(time_struct) -> datetime:
    """將 feedparser 的時間結構轉換為 datetime"""
    if time_struct is None:
        return datetime.now()
    try:
        return datetime(*time_struct[:6])
    except (TypeError, ValueError):
        return datetime.now()


def parse_rss(url: str) -> PodcastInfo:
    """
    解析 RSS Feed 並返回 Podcast 資訊
    
    Args:
        url: RSS Feed 的 URL
        
    Returns:
        PodcastInfo: 包含頻道資訊和所有集數的物件
        
    Raises:
        ValueError: 如果 URL 無效或無法解析
    """
    feed = feedparser.parse(url)
    
    # 檢查是否解析成功
    if feed.bozo and not feed.entries:
        raise ValueError(f"無法解析 RSS Feed: {feed.bozo_exception}")
    
    # 取得頻道資訊
    channel = feed.feed
    title = getattr(channel, 'title', '未知頻道')
    description = getattr(channel, 'description', '')
    image_url = None
    if hasattr(channel, 'image') and hasattr(channel.image, 'href'):
        image_url = channel.image.href
    
    # 解析所有集數
    episodes = []
    for entry in feed.entries:
        # 尋找音檔連結
        audio_url = None
        file_size = 0
        
        # 通常在 enclosures 裡面
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if 'audio' in enclosure.get('type', ''):
                    audio_url = enclosure.get('href')
                    file_size = int(enclosure.get('length', 0) or 0)
                    break
        
        # 如果沒有 enclosure，嘗試從 links 取得
        if not audio_url and hasattr(entry, 'links'):
            for link in entry.links:
                if 'audio' in link.get('type', ''):
                    audio_url = link.get('href')
                    break
        
        # 如果還是找不到音檔連結，跳過這一集
        if not audio_url:
            continue
        
        # 取得發布時間
        published = parse_time_struct(
            getattr(entry, 'published_parsed', None) or
            getattr(entry, 'updated_parsed', None)
        )
        
        # 取得時長（itunes:duration）
        duration = getattr(entry, 'itunes_duration', '')
        
        episode = Episode(
            index=0,  # 稍後重新編號
            title=entry.get('title', '無標題'),
            published=published,
            audio_url=audio_url,
            duration=str(duration),
            file_size=file_size
        )
        episodes.append(episode)
    
    # 按照發布時間排序（從舊到新）並重新編號
    episodes.sort(key=lambda e: e.published)
    for i, ep in enumerate(episodes, start=1):
        ep.index = i
    
    return PodcastInfo(
        title=title,
        description=description,
        image_url=image_url,
        episodes=episodes
    )


if __name__ == "__main__":
    # 簡單測試
    test_url = "https://feed.firstory.me/rss/user/clcftm46z000201z45w1c47fi"
    info = parse_rss(test_url)
    print(f"頻道名稱: {info.title}")
    print(f"集數: {len(info.episodes)}")
    for ep in info.episodes[:3]:
        print(f"  EP{ep.index:03d}: {ep.title[:40]}... ({ep.published.date()})")
