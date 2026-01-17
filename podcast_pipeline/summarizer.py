"""
Summarizer - 摘要生成器

負責：
1. 載入和管理摘要模板
2. 使用 Ollama 進行逐字稿潤稿
3. 生成結構化摘要
"""

import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .ollama_client import OllamaClient, LLMResponse


@dataclass
class SummaryResult:
    """摘要結果"""
    success: bool
    polished_transcript: Optional[str] = None
    summary: Optional[str] = None
    template_used: Optional[str] = None
    error: Optional[str] = None


class Summarizer:
    """摘要生成器"""
    
    def __init__(self, ollama_client: OllamaClient, templates_path: Optional[Path] = None):
        """
        初始化摘要生成器
        
        Args:
            ollama_client: Ollama 客戶端實例
            templates_path: 模板設定檔路徑
        """
        self.ollama = ollama_client
        self.templates_path = templates_path or Path(__file__).parent.parent / "config" / "templates.yaml"
        self.templates = self._load_templates()
    
    def _load_templates(self) -> dict:
        """載入模板設定"""
        if self.templates_path.exists():
            with open(self.templates_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('templates', {})
        return self._get_default_templates()
    
    def _get_default_templates(self) -> dict:
        """取得預設模板"""
        return {
            'stock_analysis': {
                'name': '股票財經分析',
                'description': '專注於提取股票、公司、數字、展望等財經資訊',
                'polish_prompt': '''你是一位專業的繁體中文編輯。請幫我潤飾以下 Podcast 逐字稿：

1. 修正明顯的語音辨識錯誤
2. 補上適當的標點符號
3. 保留原意，不要大幅修改內容
4. 專有名詞（公司名、股票代號）要正確

逐字稿內容：
{transcript}

請直接輸出潤飾後的文字，不需要額外說明。''',
                'summary_prompt': '''你是一位財經 Podcast 摘要專家。請根據以下逐字稿，產生結構化的摘要。

特別注意提取：
- 📈 提到的**公司名稱**和**股票代號**
- 📊 提到的**具體數字**（股價、漲跌幅、營收、EPS 等）
- 🔮 對市場或公司的**展望和預測**
- 📰 重要的**新聞事件**或**產業動態**

逐字稿：
{transcript}

請用以下格式輸出（Markdown）：

# {episode_title}

## 📌 一句話摘要
（用一句話概括這集的核心內容）

## 📈 提及的公司與股票
| 公司/股票 | 代號 | 相關數據 | 展望/評論 |
|---------|------|---------|----------|
| ... | ... | ... | ... |

## 🎯 重點整理
1. ...
2. ...
3. ...

## 📝 詳細內容

### 話題一：...
- ...

### 話題二：...
- ...

## 💡 金句
> "..."

## 🔮 展望與預測
- ...'''
            },
            'default': {
                'name': '通用摘要',
                'description': '適用於各類型 Podcast',
                'polish_prompt': '''你是一位專業的繁體中文編輯。請幫我潤飾以下 Podcast 逐字稿：

1. 修正明顯的語音辨識錯誤
2. 補上適當的標點符號
3. 保留原意，不要大幅修改內容

逐字稿內容：
{transcript}

請直接輸出潤飾後的文字，不需要額外說明。''',
                'summary_prompt': '''你是一位 Podcast 摘要專家。請根據以下逐字稿，產生結構化的摘要。

逐字稿：
{transcript}

請用以下格式輸出（Markdown）：

# {episode_title}

## 📌 一句話摘要
（用一句話概括這集的核心內容）

## 🎯 重點整理
1. ...
2. ...
3. ...

## 📝 詳細內容

### 話題一：...
- ...

### 話題二：...
- ...

## 💡 金句
> "..."'''
            }
        }
    
    def reload_templates(self):
        """重新載入模板"""
        self.templates = self._load_templates()
    
    def get_template_names(self) -> list[str]:
        """取得所有模板名稱"""
        return list(self.templates.keys())
    
    def get_template_info(self, template_name: str) -> Optional[dict]:
        """取得模板資訊"""
        template = self.templates.get(template_name)
        if template:
            return {
                'name': template.get('name', template_name),
                'description': template.get('description', '')
            }
        return None
    
    def polish_transcript(
        self, 
        transcript: str,
        template_name: str = 'default'
    ) -> LLMResponse:
        """
        潤飾逐字稿
        
        Args:
            transcript: 原始逐字稿
            template_name: 使用的模板名稱
            
        Returns:
            LLMResponse 物件
        """
        template = self.templates.get(template_name, self.templates.get('default'))
        
        if not template:
            return LLMResponse(success=False, error=f"找不到模板：{template_name}")
        
        prompt = template['polish_prompt'].format(transcript=transcript)
        
        print(f"✨ 開始潤稿（使用模板：{template.get('name', template_name)}）...")
        return self.ollama.generate(prompt, timeout=600)
    
    def generate_summary(
        self,
        transcript: str,
        episode_title: str,
        template_name: str = 'default'
    ) -> LLMResponse:
        """
        生成摘要
        
        Args:
            transcript: 逐字稿（建議先潤稿）
            episode_title: 集數標題
            template_name: 使用的模板名稱
            
        Returns:
            LLMResponse 物件
        """
        template = self.templates.get(template_name, self.templates.get('default'))
        
        if not template:
            return LLMResponse(success=False, error=f"找不到模板：{template_name}")
        
        prompt = template['summary_prompt'].format(
            transcript=transcript,
            episode_title=episode_title
        )
        
        print(f"📝 開始生成摘要（使用模板：{template.get('name', template_name)}）...")
        return self.ollama.generate(prompt, timeout=600)
    
    def process(
        self,
        transcript: str,
        episode_title: str,
        template_name: str = 'stock_analysis',
        skip_polish: bool = False
    ) -> SummaryResult:
        """
        完整處理流程：潤稿 + 摘要
        
        Args:
            transcript: 原始逐字稿
            episode_title: 集數標題
            template_name: 使用的模板名稱
            skip_polish: 是否跳過潤稿步驟
            
        Returns:
            SummaryResult 物件
        """
        polished = transcript
        
        # 步驟 1：潤稿（可選）
        if not skip_polish:
            polish_result = self.polish_transcript(transcript, template_name)
            if polish_result.success:
                polished = polish_result.content
                print(f"✅ 潤稿完成（使用模型：{polish_result.model}）")
            else:
                print(f"⚠️ 潤稿失敗：{polish_result.error}，使用原始逐字稿繼續")
        
        # 步驟 2：生成摘要
        summary_result = self.generate_summary(polished, episode_title, template_name)
        
        if summary_result.success:
            print(f"✅ 摘要生成完成（使用模型：{summary_result.model}）")
            return SummaryResult(
                success=True,
                polished_transcript=polished,
                summary=summary_result.content,
                template_used=template_name
            )
        else:
            return SummaryResult(
                success=False,
                polished_transcript=polished,
                error=f"摘要生成失敗：{summary_result.error}"
            )
    
    def save_template(self, template_name: str, template_data: dict) -> bool:
        """
        儲存自訂模板
        
        Args:
            template_name: 模板名稱（英文）
            template_data: 模板內容，包含 name, description, polish_prompt, summary_prompt
            
        Returns:
            是否成功
        """
        try:
            # 讀取現有設定
            if self.templates_path.exists():
                with open(self.templates_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
            else:
                data = {'templates': {}}
            
            # 更新模板
            if 'templates' not in data:
                data['templates'] = {}
            
            data['templates'][template_name] = template_data
            
            # 寫入檔案
            with open(self.templates_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            
            # 重新載入
            self.reload_templates()
            
            print(f"✅ 模板 '{template_name}' 已儲存")
            return True
            
        except Exception as e:
            print(f"❌ 儲存模板失敗：{e}")
            return False


    def format_transcript_for_display(
        self,
        polished_transcript: str,
        episode_title: str,
        podcast_name: str = "",
        audio_url: str = ""
    ) -> str:
        """
        將潤稿後的逐字稿格式化為 Markdown 顯示格式
        
        Args:
            polished_transcript: 潤稿後的逐字稿
            episode_title: 集數標題
            podcast_name: Podcast 名稱
            audio_url: 音訊 URL（用於播放器）
            
        Returns:
            格式化後的 Markdown 內容
        """
        # 建立 frontmatter
        frontmatter_lines = [
            "---",
            f"title: {episode_title} - 逐字稿",
            f"podcast: {podcast_name}" if podcast_name else "",
            f"audioUrl: {audio_url}" if audio_url else "",
            "---",
            ""
        ]
        frontmatter = "\n".join(line for line in frontmatter_lines if line or line == "")
        
        # 標題區塊
        header = f"# 📝 {episode_title}\n\n"
        if podcast_name:
            header += f"> 📻 節目：{podcast_name}\n\n"
        
        # 處理逐字稿內容 - 分段落
        paragraphs = polished_transcript.strip().split("\n\n")
        formatted_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 簡單的段落格式化 - 加上適當的排版
            # 如果段落很長，保持原樣
            # 如果看起來像對話（有冒號分隔），保留格式
            if "：" in para[:50] or ":" in para[:50]:
                # 可能是對話格式，嘗試格式化
                lines = para.split("\n")
                formatted_lines = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    formatted_lines.append(line)
                formatted_paragraphs.append("\n".join(formatted_lines))
            else:
                # 一般段落
                formatted_paragraphs.append(para)
        
        # 組合最終內容
        content = frontmatter + header + "---\n\n" + "\n\n".join(formatted_paragraphs)
        
        return content


# 測試用
if __name__ == "__main__":
    from .ollama_client import OllamaClient
    
    ollama_config = {
        'local': {
            'primary_url': 'http://localhost:11434',
            'model': 'gemma3:27b'
        },
        'cloud': {'enabled': False},
        'priority': ['local']
    }
    
    ollama = OllamaClient(ollama_config)
    summarizer = Summarizer(ollama)
    
    print("📋 可用模板：")
    for name in summarizer.get_template_names():
        info = summarizer.get_template_info(name)
        print(f"  - {name}: {info['name']} - {info['description']}")
