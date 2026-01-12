"""
圖形介面模組
使用 Tkinter 建立 RSS Podcast 下載器的 GUI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
from typing import List, Optional

from .parser import parse_rss, PodcastInfo, Episode
from .downloader import download_episodes, DownloadError


class PodcastDownloaderApp:
    """RSS Podcast 下載器主視窗"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RSS Podcast 下載器")
        self.root.geometry("800x650")
        self.root.minsize(700, 550)
        
        # 狀態變數
        self.podcast_info: Optional[PodcastInfo] = None
        self.episode_vars: List[tk.BooleanVar] = []
        self.is_downloading = False
        self.cancel_requested = False
        
        # 預設下載目錄
        self.download_dir = str(Path.home() / "Downloads")
        
        # 建立介面
        self._create_widgets()
        
    def _create_widgets(self):
        """建立所有 UI 元件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === RSS 輸入區 ===
        input_frame = ttk.LabelFrame(main_frame, text="RSS 連結", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.url_entry = ttk.Entry(input_frame, width=70)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.url_entry.insert(0, "https://feed.firstory.me/rss/user/clcftm46z000201z45w1c47fi")
        
        self.load_btn = ttk.Button(input_frame, text="載入", command=self._load_rss)
        self.load_btn.pack(side=tk.RIGHT)
        
        # === Podcast 資訊區 ===
        info_frame = ttk.LabelFrame(main_frame, text="Podcast 資訊", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.info_label = ttk.Label(info_frame, text="請輸入 RSS 連結並點擊「載入」")
        self.info_label.pack(anchor=tk.W)
        
        # === 選擇控制區 ===
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 全選/全不選
        self.select_all_var = tk.BooleanVar(value=False)
        self.select_all_cb = ttk.Checkbutton(
            control_frame, 
            text="全選", 
            variable=self.select_all_var,
            command=self._toggle_select_all
        )
        self.select_all_cb.pack(side=tk.LEFT)
        
        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 範圍選擇
        ttk.Label(control_frame, text="從第").pack(side=tk.LEFT)
        self.from_entry = ttk.Entry(control_frame, width=5)
        self.from_entry.pack(side=tk.LEFT, padx=3)
        self.from_entry.insert(0, "1")
        
        ttk.Label(control_frame, text="集到第").pack(side=tk.LEFT)
        self.to_entry = ttk.Entry(control_frame, width=5)
        self.to_entry.pack(side=tk.LEFT, padx=3)
        self.to_entry.insert(0, "10")
        
        ttk.Label(control_frame, text="集").pack(side=tk.LEFT)
        
        self.range_btn = ttk.Button(control_frame, text="套用範圍", command=self._apply_range)
        self.range_btn.pack(side=tk.LEFT, padx=10)
        
        # 選中數量標籤
        self.selected_label = ttk.Label(control_frame, text="已選: 0 集")
        self.selected_label.pack(side=tk.RIGHT)
        
        # === 集數列表區 ===
        list_frame = ttk.LabelFrame(main_frame, text="集數列表", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 建立 Canvas 和 Scrollbar 實現可捲動的勾選框列表
        self.canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.episodes_frame = ttk.Frame(self.canvas)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.episodes_frame, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 綁定滾輪事件
        self.episodes_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # === 下載設定區 ===
        download_frame = ttk.LabelFrame(main_frame, text="下載設定", padding="10")
        download_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(download_frame, text="下載目錄:").pack(side=tk.LEFT)
        
        self.dir_entry = ttk.Entry(download_frame, width=50)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.dir_entry.insert(0, self.download_dir)
        
        self.dir_btn = ttk.Button(download_frame, text="選擇目錄", command=self._select_directory)
        self.dir_btn.pack(side=tk.RIGHT)
        
        # === 進度區 ===
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.progress_label = ttk.Label(progress_frame, text="")
        self.progress_label.pack(anchor=tk.W)
        
        # === 按鈕區 ===
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.download_btn = ttk.Button(
            button_frame, 
            text="開始下載", 
            command=self._start_download,
            state=tk.DISABLED
        )
        self.download_btn.pack(side=tk.RIGHT)
        
        self.cancel_btn = ttk.Button(
            button_frame,
            text="取消下載",
            command=self._cancel_download,
            state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=10)
        
    def _on_frame_configure(self, event):
        """更新 Canvas 可捲動區域"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_canvas_configure(self, event):
        """調整內部框架寬度以填滿 Canvas"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def _on_mousewheel(self, event):
        """處理滑鼠滾輪事件"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
    def _load_rss(self):
        """載入 RSS Feed"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("警告", "請輸入 RSS 連結")
            return
            
        # 顯示載入中
        self.load_btn.config(state=tk.DISABLED)
        self.info_label.config(text="載入中...")
        self.root.update()
        
        try:
            self.podcast_info = parse_rss(url)
            self._display_episodes()
            self.info_label.config(
                text=f"📻 {self.podcast_info.title}    |    共 {len(self.podcast_info.episodes)} 集"
            )
            self.download_btn.config(state=tk.NORMAL)
            # 更新範圍輸入框
            self.to_entry.delete(0, tk.END)
            self.to_entry.insert(0, str(len(self.podcast_info.episodes)))
            
        except Exception as e:
            messagebox.showerror("錯誤", f"無法載入 RSS:\n{e}")
            self.info_label.config(text="載入失敗")
            
        finally:
            self.load_btn.config(state=tk.NORMAL)
            
    def _display_episodes(self):
        """顯示集數列表"""
        # 清除舊的
        for widget in self.episodes_frame.winfo_children():
            widget.destroy()
        self.episode_vars.clear()
        
        if not self.podcast_info:
            return
            
        for ep in self.podcast_info.episodes:
            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *args: self._update_selected_count())
            self.episode_vars.append(var)
            
            frame = ttk.Frame(self.episodes_frame)
            frame.pack(fill=tk.X, pady=1)
            
            cb = ttk.Checkbutton(frame, variable=var)
            cb.pack(side=tk.LEFT)
            
            # 集數編號
            ep_label = ttk.Label(frame, text=f"EP{ep.index:03d}", width=6, foreground="#666666")
            ep_label.pack(side=tk.LEFT)
            
            # 標題
            title_text = ep.title[:60] + "..." if len(ep.title) > 60 else ep.title
            title_label = ttk.Label(frame, text=title_text)
            title_label.pack(side=tk.LEFT, padx=5)
            
            # 日期
            date_label = ttk.Label(frame, text=ep.published.strftime("%Y-%m-%d"), foreground="#888888")
            date_label.pack(side=tk.RIGHT, padx=10)
            
        self._update_selected_count()
            
    def _toggle_select_all(self):
        """全選/全不選切換"""
        value = self.select_all_var.get()
        for var in self.episode_vars:
            var.set(value)
            
    def _apply_range(self):
        """套用範圍選擇"""
        try:
            from_idx = int(self.from_entry.get())
            to_idx = int(self.to_entry.get())
        except ValueError:
            messagebox.showwarning("警告", "請輸入有效的數字")
            return
            
        if from_idx < 1:
            from_idx = 1
        if to_idx > len(self.episode_vars):
            to_idx = len(self.episode_vars)
            
        if from_idx > to_idx:
            messagebox.showwarning("警告", "起始集數不能大於結束集數")
            return
            
        # 先全部取消選擇
        for var in self.episode_vars:
            var.set(False)
            
        # 選擇範圍內的
        for i in range(from_idx - 1, to_idx):
            self.episode_vars[i].set(True)
            
        self.select_all_var.set(False)
        
    def _update_selected_count(self):
        """更新已選數量"""
        count = sum(1 for var in self.episode_vars if var.get())
        self.selected_label.config(text=f"已選: {count} 集")
        
    def _select_directory(self):
        """選擇下載目錄"""
        directory = filedialog.askdirectory(initialdir=self.download_dir)
        if directory:
            self.download_dir = directory
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)
            
    def _get_selected_episodes(self) -> List[Episode]:
        """取得已選擇的集數"""
        if not self.podcast_info:
            return []
        return [
            ep for ep, var in zip(self.podcast_info.episodes, self.episode_vars)
            if var.get()
        ]
        
    def _start_download(self):
        """開始下載"""
        episodes = self._get_selected_episodes()
        if not episodes:
            messagebox.showwarning("警告", "請選擇至少一集")
            return
            
        output_dir = self.dir_entry.get().strip()
        if not output_dir:
            messagebox.showwarning("警告", "請選擇下載目錄")
            return
            
        # 確認
        confirm = messagebox.askyesno(
            "確認下載",
            f"即將下載 {len(episodes)} 集到:\n{output_dir}\n\n確定要開始嗎?"
        )
        if not confirm:
            return
            
        # 開始下載
        self.is_downloading = True
        self.cancel_requested = False
        self._toggle_ui_state(False)
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = len(episodes)
        
        # 在背景執行緒中下載
        thread = threading.Thread(
            target=self._download_thread,
            args=(episodes, output_dir)
        )
        thread.daemon = True
        thread.start()
        
    def _download_thread(self, episodes: List[Episode], output_dir: str):
        """下載執行緒"""
        def overall_progress(done, total, filename):
            self.root.after(0, lambda: self._update_overall_progress(done, total, filename))
            
        def file_progress(done, total):
            if total > 0:
                pct = done / total * 100
                self.root.after(0, lambda p=pct: self._update_file_progress(p))
                
        def check_cancel():
            return self.cancel_requested
            
        try:
            downloaded = download_episodes(
                episodes,
                output_dir,
                overall_progress_callback=overall_progress,
                file_progress_callback=file_progress,
                cancel_check=check_cancel
            )
            
            # 完成
            self.root.after(0, lambda: self._download_complete(len(downloaded), len(episodes)))
            
        except Exception as e:
            self.root.after(0, lambda: self._download_error(str(e)))
            
    def _update_overall_progress(self, done: int, total: int, filename: str):
        """更新整體進度"""
        self.progress_bar["value"] = done
        if filename == "完成":
            self.progress_label.config(text="下載完成！")
        else:
            self.progress_label.config(text=f"下載中 ({done}/{total}): {filename}")
            
    def _update_file_progress(self, percent: float):
        """更新單檔進度（可選顯示）"""
        pass  # 目前只顯示整體進度
        
    def _download_complete(self, success_count: int, total_count: int):
        """下載完成"""
        self.is_downloading = False
        self._toggle_ui_state(True)
        
        if self.cancel_requested:
            messagebox.showinfo("已取消", f"下載已取消\n成功下載: {success_count}/{total_count} 集")
        else:
            messagebox.showinfo("完成", f"下載完成！\n成功下載: {success_count}/{total_count} 集")
            
    def _download_error(self, error: str):
        """下載發生錯誤"""
        self.is_downloading = False
        self._toggle_ui_state(True)
        messagebox.showerror("錯誤", f"下載時發生錯誤:\n{error}")
        
    def _cancel_download(self):
        """取消下載"""
        self.cancel_requested = True
        self.progress_label.config(text="正在取消...")
        
    def _toggle_ui_state(self, enabled: bool):
        """切換 UI 狀態"""
        state = tk.NORMAL if enabled else tk.DISABLED
        self.load_btn.config(state=state)
        self.url_entry.config(state=state)
        self.download_btn.config(state=state)
        self.dir_btn.config(state=state)
        self.range_btn.config(state=state)
        self.select_all_cb.config(state=state)
        
        # 取消按鈕相反
        self.cancel_btn.config(state=tk.DISABLED if enabled else tk.NORMAL)


def run_app():
    """啟動應用程式"""
    root = tk.Tk()
    app = PodcastDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_app()
