# Podcast Pipeline API Specification

## 概述

Dashboard 提供 REST API 供前端或外部系統使用。

**Base URL**: `http://localhost:8080`

---

## Endpoints

### 系統狀態

#### `GET /api/status`

取得系統連線狀態。

**Response:**

```json
{
  "whisper": {
    "connected": true,
    "input_dir": "/Volumes/whisper/whisper.cpp/input",
    "output_dir": "/Volumes/whisper/whisper.cpp/output"
  },
  "ollama": {
    "local": {
      "primary": { "url": "http://YOUR_WINDOWS_IP:11434", "connected": true },
      "fallback": { "url": "http://localhost:11434", "connected": false }
    },
    "model": "gemma3:27b"
  },
  "telegram": {
    "enabled": true,
    "chat_id": "@twpodcast"
  }
}
```

---

### RSS Feed 管理

#### `GET /api/feeds`

取得已訂閱的 RSS Feed 列表。

#### `POST /api/feeds/save`

儲存 Feed 設定。

#### `POST /api/parse`

解析 RSS Feed。

**Request:**

```json
{
  "url": "https://feed.firstory.me/rss/user/xxx"
}
```

---

### 排程設定

#### `GET /api/schedule`

取得排程設定。

**Response:**

```json
{
  "enabled": true,
  "times": ["10:00", "21:00"],
  "max_episodes": 3
}
```

#### `POST /api/schedule/save`

儲存排程設定。

---

### 下載與處理

#### `POST /api/download_and_copy`

下載音檔並複製到 Whisper input 資料夾。

**Request:**

```json
{
  "episode": {
    "index": 589,
    "title": "...",
    "audio_url": "https://..."
  },
  "feed_name": "財報狗",
  "feed_prefix": "CFG"
}
```

**Response:**

```json
{
  "success": true,
  "file_stem": "CFG_EP589"
}
```

---

### 自動監控

#### `POST /api/watcher/start`

啟動自動監控。

#### `POST /api/watcher/stop`

停止自動監控。

#### `GET /api/watcher/status`

取得監控狀態和排程日誌。

**Response:**

```json
{
  "running": true,
  "processed_count": 5,
  "pending_count": 0,
  "last_check": "13:25:30",
  "logs": [...],
  "scheduler_logs": [...],
  "scheduler_last_run": "2026-01-12 10:00:05"
}
```

---

### Telegram 控制

#### `GET /api/telegram/broadcast`

取得廣播開關狀態。

#### `POST /api/telegram/broadcast`

設定廣播開關。

**Request:**

```json
{
  "enabled": false
}
```

#### `POST /api/telegram/send`

手動發送單個摘要到 Telegram。

**Request:**

```json
{
  "summary_name": "財報狗EP589"
}
```

**Response:**

```json
{
  "success": true
}
```

---

### 摘要管理

#### `GET /api/summaries`

取得摘要列表。

**Response:**

```json
[
  { "name": "財報狗EP590", "preview": "..." },
  { "name": "股癌EP626", "preview": "..." }
]
```

#### `GET /api/summary/<name>`

取得單一摘要內容 (Markdown)。

---

### 模板管理

#### `GET /api/templates`

取得所有模板。

#### `POST /api/templates/save`

儲存模板。

#### `POST /api/templates/delete`

刪除自訂模板。

---

## 設定檔規格

### `config/services.yaml`

| 欄位 | 類型 | 說明 |
|------|------|------|
| `whisper.input_dir` | string | Whisper 輸入資料夾路徑 |
| `whisper.output_dir` | string | Whisper 輸出資料夾路徑 |
| `ollama.local.primary_url` | string | Windows Ollama URL |
| `ollama.local.models` | array | 模型列表 |
| `telegram.enabled` | boolean | 是否啟用 Telegram |
| `telegram.bot_token` | string | Bot Token |
| `telegram.chat_id` | string | 頻道或群組 ID |

### `config/feeds.yaml`

```yaml
feeds:
  - name: "財報狗"
    prefix: "CFG"
    template: "cfg_financial_dog"
    url: "https://..."
    enabled: true
```

### `config/templates.yaml`

內建模板：

- `stock_analysis` - 股票財經通用
- `cfg_financial_dog` - 財報狗專屬
- `gooaye` - 股癌專屬
- `mdj_money_dj` - Money DJ 專屬

---

## 重要資料檔

| 檔案 | 用途 | 可刪除? |
|------|------|--------|
| `data/episode_metadata.json` | 逐字稿-摘要對照 | ❌ 勿刪 |
| `data/broadcasted.json` | 已推送記錄 | ⚠️ 刪除會重複推送 |
| `data/summaries/*.md` | 摘要檔案 | ✅ 可刪除重生成 |
| `data/schedule_config.json` | 排程設定 | ✅ 可刪除 |

---

## 排除規則

自動監控會排除以下前綴的檔案：

- `S3EP` - 成人節目

可在 `dashboard.py` 的 `EXCLUDE_PREFIXES` 變數修改。
