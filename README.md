# RSS Podcast 一條龍自動化系統

透過 RSS 追蹤 Podcast，自動下載 → Whisper 轉錄 → Ollama 摘要 → Telegram 推送。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-macOS-lightgrey.svg)

🌐 **線上摘要庫**：[https://liuxvuse.github.io/TWpodcast/summaries/](https://liuxvuse.github.io/TWpodcast/summaries/)

## ✨ 功能

| 功能 | 說明 |
|------|------|
| 📥 RSS 下載 | 多選批次下載 Podcast 音檔 |
| 📅 **排程掃描** | 定時自動掃描 RSS 並下載新集數 |
| 🎙️ Whisper 整合 | 透過 SMB 與 Windows 電腦整合轉錄 |
| 🤖 Ollama 摘要 | 支援 Gemma 3 27B，自動模型冷卻機制 |
| 📋 自訂模板 | 財報狗、股癌、Money DJ 專屬模板 |
| 🔄 自動監控 | 新逐字稿自動生成摘要 |
| 🎧 **網頁播放器** | 在摘要頁面直接播放該集 Podcast |
| �📤 **Telegram 推送** | 自動/手動推送摘要，支援批量發送 |
| 🚀 **Git 自動發布** | 摘要生成後自動推送到 GitHub，並自動同步網站目錄 |
| 🔄 **SMB 自動補傳** | SMB 斷線重連後自動補傳待處理的音檔 |
| 🌐 Web Dashboard | 現代化管理介面 |

## 🚀 快速開始

```bash
# 1. 進入專案
cd /Users/liu/Documents/porject/RSSpodcast

# 2. 啟動虛擬環境
source .venv/bin/activate

# 3. 啟動 Dashboard
python dashboard.py

# 4. 開啟瀏覽器
# http://localhost:8080
```

## 📁 專案結構

```
RSSpodcast/
├── config/                 # 設定檔
│   ├── services.yaml       # Whisper/Ollama/Telegram 設定
│   ├── feeds.yaml          # RSS Feed 設定
│   └── templates.yaml      # 摘要模板
├── podcast_pipeline/       # 核心模組
│   ├── whisper_bridge.py   # Windows Whisper 整合
│   ├── ollama_client.py    # LLM 客戶端（含冷卻機制）
│   ├── summarizer.py       # 摘要生成器（含逐字稿格式化）
│   ├── telegram_notifier.py # Telegram 推送
│   └── pipeline.py         # 流程管理
├── site/                   # VitePress 網站
│   ├── summaries/          # 摘要 Markdown（含播放器 frontmatter）
│   ├── transcripts/        # 潤稿逐字稿 Markdown
│   └── .vitepress/theme/   # 自訂組件（AudioPlayer 等）
├── data/
│   ├── tracking.db         # 處理記錄
│   ├── summaries/          # 生成的摘要
│   ├── episode_metadata.json # 集數對照表（重要！勿刪）
│   └── broadcasted.json    # 已廣播記錄
├── dashboard.py            # Web UI (主程式)
├── auto_watcher.py         # 自動監控器 v2.0
└── requirements.txt
```

## 🔐 關鍵檔案（碰不得）

| 檔案 | 作用 |
|------|------|
| `data/episode_metadata.json` | 逐字稿與摘要的對照表 |
| `data/broadcasted.json` | 已推送到 Telegram 的記錄 |
| `config/*.yaml` | 所有設定檔 |

## ⚙️ 設定

### Whisper 路徑

```yaml
# config/services.yaml
whisper:
  input_dir: "/Volumes/whisper/whisper.cpp/input"
  output_dir: "/Volumes/whisper/whisper.cpp/output"
```

### Ollama 設定

```yaml
ollama:
  local:
    primary_url: "http://YOUR_WINDOWS_IP:11434"  # 填入您的 Windows IP
    models:
      - "gemma3:27b"
  priority: ["local"]
```

### Telegram 設定

```yaml
telegram:
  enabled: true
  bot_token: "xxx"
  chat_id: "@your_channel"
```

### 排程設定

在 Dashboard「RSS 訂閱」頁面設定：

- **掃描時間**：如 `10:00, 21:00`
- **下載集數**：每次掃描最多下載幾集

## 📤 Telegram 功能

| 功能 | 說明 |
|------|------|
| 自動推送 | 摘要生成後自動推送 |
| 廣播開關 | 測試時可關閉，不會推送 |
| 批量發送 | 勾選多個摘要一次發送 |
| 發送順序 | EP 數字小的先發 |
| 防重複 | 已推送的不會重複發送 |

## 🔧 API

詳見 [API_SPEC.md](./API_SPEC.md)

## 📦 依賴

```
feedparser, requests, flask, pyyaml, tqdm
```

## 📄 License

MIT
