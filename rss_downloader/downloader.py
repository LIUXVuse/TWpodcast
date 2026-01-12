"""
音檔下載模組
處理 Podcast 音檔的下載功能
"""

import os
import requests
from typing import Callable, Optional, List
from pathlib import Path

from .parser import Episode


class DownloadError(Exception):
    """下載過程中發生的錯誤"""
    pass


def download_episode(
    episode: Episode,
    output_dir: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> str:
    """
    下載單一集數的音檔
    
    Args:
        episode: 要下載的集數
        output_dir: 輸出目錄
        progress_callback: 進度回呼函數 (已下載 bytes, 總 bytes)
        cancel_check: 檢查是否要取消下載的函數
        
    Returns:
        str: 下載完成的檔案路徑
        
    Raises:
        DownloadError: 下載失敗時
    """
    # 確保輸出目錄存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 產生檔案名稱
    filename = episode.get_filename()
    filepath = output_path / filename
    
    # 如果檔案已存在，跳過下載
    if filepath.exists():
        file_size = filepath.stat().st_size
        if file_size > 0:
            if progress_callback:
                progress_callback(file_size, file_size)
            return str(filepath)
    
    try:
        # 發送請求
        response = requests.get(episode.audio_url, stream=True, timeout=30)
        response.raise_for_status()
        
        # 取得檔案大小
        total_size = int(response.headers.get('content-length', 0))
        if total_size == 0:
            total_size = episode.file_size
        
        # 開始下載
        downloaded = 0
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                # 檢查是否要取消
                if cancel_check and cancel_check():
                    f.close()
                    filepath.unlink(missing_ok=True)
                    raise DownloadError("下載已取消")
                
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # 回報進度
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        
        return str(filepath)
        
    except requests.RequestException as e:
        # 清理未完成的檔案
        filepath.unlink(missing_ok=True)
        raise DownloadError(f"下載失敗: {e}")


def download_episodes(
    episodes: List[Episode],
    output_dir: str,
    overall_progress_callback: Optional[Callable[[int, int, str], None]] = None,
    file_progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None
) -> List[str]:
    """
    批次下載多個集數
    
    Args:
        episodes: 要下載的集數列表
        output_dir: 輸出目錄
        overall_progress_callback: 整體進度回呼 (已完成數, 總數, 當前檔名)
        file_progress_callback: 單檔進度回呼 (已下載 bytes, 總 bytes)
        cancel_check: 檢查是否要取消的函數
        
    Returns:
        List[str]: 成功下載的檔案路徑列表
    """
    downloaded_files = []
    total = len(episodes)
    
    for i, episode in enumerate(episodes):
        # 檢查取消
        if cancel_check and cancel_check():
            break
            
        # 回報整體進度
        if overall_progress_callback:
            overall_progress_callback(i, total, episode.get_filename())
        
        try:
            filepath = download_episode(
                episode,
                output_dir,
                progress_callback=file_progress_callback,
                cancel_check=cancel_check
            )
            downloaded_files.append(filepath)
        except DownloadError as e:
            print(f"下載 {episode.title} 時發生錯誤: {e}")
            continue
    
    # 完成
    if overall_progress_callback:
        overall_progress_callback(total, total, "完成")
    
    return downloaded_files


if __name__ == "__main__":
    # 簡單測試
    from .parser import parse_rss
    
    url = "https://feed.firstory.me/rss/user/clcftm46z000201z45w1c47fi"
    info = parse_rss(url)
    
    if info.episodes:
        ep = info.episodes[0]
        print(f"測試下載: {ep.title}")
        
        def progress(done, total):
            if total > 0:
                pct = done / total * 100
                print(f"\r下載進度: {pct:.1f}%", end="")
        
        path = download_episode(ep, "./downloads", progress_callback=progress)
        print(f"\n下載完成: {path}")
