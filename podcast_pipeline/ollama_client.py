"""
Ollama Client - LLM 整合客戶端

支援：
1. 本地 Ollama（Windows 5090 或 Mac）
2. Ollama Cloud（免費 DeepSeek V3.1）
"""

import requests
import time
from typing import Optional, Generator
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLM 回應"""
    success: bool
    content: Optional[str] = None
    model: Optional[str] = None
    source: Optional[str] = None  # 'local' or 'cloud'
    error: Optional[str] = None
    tokens_used: Optional[int] = None


class OllamaClient:
    """Ollama LLM 客戶端"""
    
    def __init__(self, config: dict):
        """
        初始化 Ollama Client
        
        Args:
            config: 設定字典，包含 local 和 cloud 設定
        """
        self.local_config = config.get('local', {})
        self.cloud_config = config.get('cloud', {})
        self.priority = config.get('priority', ['local', 'cloud'])
        
        # 本地設定
        self.local_primary_url = self.local_config.get('primary_url', 'http://localhost:11434')
        self.local_fallback_url = self.local_config.get('fallback_url', 'http://localhost:11434')
        
        # 模型優先順序（支援列表或單一模型）
        models = self.local_config.get('models', [])
        if isinstance(models, list) and models:
            self.local_models = models
        else:
            # 向後相容：單一模型
            self.local_models = [self.local_config.get('model', 'gemma3:27b')]
        
        # 模型冷卻追蹤（限流後 2 小時內不再嘗試）
        self.model_cooldown = {}  # {model_name: cooldown_until_timestamp}
        self.cooldown_duration = 2 * 60 * 60  # 2 小時
        
        # 雲端設定
        self.cloud_enabled = self.cloud_config.get('enabled', False)
        self.cloud_url = self.cloud_config.get('url', 'https://api.ollama.com/v1')
        self.cloud_model = self.cloud_config.get('model', 'deepseek-v3.1:671b-cloud')
        self.cloud_api_key = self.cloud_config.get('api_key', '')
    
    def test_connection(self, url: str) -> bool:
        """測試 Ollama 連接"""
        try:
            resp = requests.get(f"{url}/api/tags", timeout=5)
            return resp.ok
        except:
            return False
    
    def get_available_models(self, url: str) -> list[str]:
        """取得可用的模型列表"""
        try:
            resp = requests.get(f"{url}/api/tags", timeout=10)
            if resp.ok:
                data = resp.json()
                return [m['name'] for m in data.get('models', [])]
        except:
            pass
        return []
    
    def _generate_local(
        self, 
        prompt: str, 
        url: str,
        model: Optional[str] = None,
        timeout: int = 300
    ) -> LLMResponse:
        """本地 Ollama 生成"""
        model = model or self.local_model
        
        try:
            resp = requests.post(
                f"{url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=timeout
            )
            
            if resp.ok:
                data = resp.json()
                return LLMResponse(
                    success=True,
                    content=data.get('response', ''),
                    model=model,
                    source='local',
                    tokens_used=data.get('eval_count')
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except requests.Timeout:
            return LLMResponse(success=False, error="請求超時")
        except requests.RequestException as e:
            return LLMResponse(success=False, error=str(e))
    
    def _generate_cloud(
        self, 
        prompt: str,
        timeout: int = 300
    ) -> LLMResponse:
        """Ollama Cloud 生成"""
        if not self.cloud_enabled:
            return LLMResponse(success=False, error="雲端服務未啟用")
        
        headers = {}
        if self.cloud_api_key:
            headers['Authorization'] = f'Bearer {self.cloud_api_key}'
        
        try:
            # Ollama Cloud 使用類似 OpenAI 的 API
            resp = requests.post(
                f"{self.cloud_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.cloud_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                },
                timeout=timeout
            )
            
            if resp.ok:
                data = resp.json()
                content = data['choices'][0]['message']['content']
                return LLMResponse(
                    success=True,
                    content=content,
                    model=self.cloud_model,
                    source='cloud',
                    tokens_used=data.get('usage', {}).get('total_tokens')
                )
            else:
                return LLMResponse(
                    success=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except requests.Timeout:
            return LLMResponse(success=False, error="雲端請求超時")
        except requests.RequestException as e:
            return LLMResponse(success=False, error=str(e))
    
    def generate(
        self, 
        prompt: str,
        model: Optional[str] = None,
        timeout: int = 300,
        retry_count: int = 2
    ) -> LLMResponse:
        """
        生成文字，按優先順序嘗試不同服務和模型
        
        Args:
            prompt: 輸入提示詞
            model: 指定模型（可選，指定時不會嘗試其他模型）
            timeout: 超時時間（秒）
            retry_count: 每個服務的重試次數
            
        Returns:
            LLMResponse 物件
        """
        errors = []
        
        # 決定要嘗試的模型列表
        models_to_try = [model] if model else self.local_models
        
        # 過濾掉仍在冷卻中的模型
        current_time = time.time()
        available_models = []
        for m in models_to_try:
            cooldown_until = self.model_cooldown.get(m, 0)
            if current_time >= cooldown_until:
                available_models.append(m)
            else:
                remaining = int((cooldown_until - current_time) / 60)
                print(f"⏳ {m} 冷卻中，剩餘 {remaining} 分鐘，跳過")
        
        # 如果所有模型都在冷卻，清除最舊的冷卻
        if not available_models and models_to_try:
            print("⚠️ 所有模型都在冷卻中，重置冷卻狀態")
            self.model_cooldown.clear()
            available_models = models_to_try
        
        for source in self.priority:
            if source == 'local':
                # 嘗試本地服務
                for url in [self.local_primary_url, self.local_fallback_url]:
                    if not self.test_connection(url):
                        errors.append(f"[local:{url}] 無法連接")
                        continue
                    
                    # 嘗試每個模型
                    for try_model in available_models:
                        for attempt in range(retry_count):
                            print(f"🤖 嘗試 {try_model} @ {url}... (第 {attempt + 1} 次)")
                            result = self._generate_local(prompt, url, try_model, timeout)
                            
                            if result.success:
                                return result
                            
                            errors.append(f"[{try_model}@{url.split('/')[-1]}] {result.error}")
                            
                            # 如果是 429 限流錯誤，設定冷卻並換下一個模型
                            if '429' in str(result.error):
                                cooldown_until = time.time() + self.cooldown_duration
                                self.model_cooldown[try_model] = cooldown_until
                                print(f"⚠️ {try_model} 達到限制，設定 2 小時冷卻，切換下一個模型...")
                                break
                            
                            time.sleep(1)
            
            elif source == 'cloud' and self.cloud_enabled:
                # 嘗試雲端服務
                for attempt in range(retry_count):
                    print(f"☁️ 嘗試 Ollama Cloud... (第 {attempt + 1} 次)")
                    result = self._generate_cloud(prompt, timeout)
                    
                    if result.success:
                        return result
                    
                    errors.append(f"[cloud] {result.error}")
                    time.sleep(1)
        
        # 所有服務都失敗
        return LLMResponse(
            success=False,
            error=f"所有服務都無法使用：{'; '.join(errors[-5:])}"  # 只顯示最後5個錯誤
        )
    
    def generate_stream(
        self, 
        prompt: str,
        model: Optional[str] = None,
        url: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        串流生成文字（只支援本地）
        
        Args:
            prompt: 輸入提示詞
            model: 指定模型
            url: 指定 URL
            
        Yields:
            生成的文字片段
        """
        url = url or self.local_primary_url
        model = model or self.local_model
        
        try:
            resp = requests.post(
                f"{url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": True
                },
                stream=True,
                timeout=300
            )
            
            if resp.ok:
                for line in resp.iter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if 'response' in data:
                            yield data['response']
        except Exception as e:
            yield f"\n[錯誤：{e}]"
    
    def get_status(self) -> dict:
        """取得所有服務的連接狀態"""
        status = {
            'local': {
                'primary': {
                    'url': self.local_primary_url,
                    'connected': self.test_connection(self.local_primary_url),
                    'models': []
                },
                'fallback': {
                    'url': self.local_fallback_url,
                    'connected': self.test_connection(self.local_fallback_url),
                    'models': []
                },
                'default_model': self.local_models[0] if self.local_models else 'N/A'
            },
            'cloud': {
                'enabled': self.cloud_enabled,
                'model': self.cloud_model
            }
        }
        
        # 取得可用模型
        if status['local']['primary']['connected']:
            status['local']['primary']['models'] = self.get_available_models(self.local_primary_url)
        if status['local']['fallback']['connected']:
            status['local']['fallback']['models'] = self.get_available_models(self.local_fallback_url)
        
        return status


# 測試用
if __name__ == "__main__":
    config = {
        'local': {
            'primary_url': 'http://192.168.1.100:11434',
            'fallback_url': 'http://localhost:11434',
            'model': 'gemma3:27b'
        },
        'cloud': {
            'enabled': True,
            'url': 'https://api.ollama.com/v1',
            'model': 'deepseek-v3.1:671b-cloud',
            'api_key': ''
        },
        'priority': ['local', 'cloud']
    }
    
    client = OllamaClient(config)
    
    print("📊 Ollama 服務狀態：")
    status = client.get_status()
    
    print(f"\n本地主要服務 ({status['local']['primary']['url']}):")
    print(f"  連接：{'✅' if status['local']['primary']['connected'] else '❌'}")
    if status['local']['primary']['models']:
        print(f"  模型：{', '.join(status['local']['primary']['models'][:5])}")
    
    print(f"\n本地備用服務 ({status['local']['fallback']['url']}):")
    print(f"  連接：{'✅' if status['local']['fallback']['connected'] else '❌'}")
    
    print(f"\n雲端服務：{'啟用' if status['cloud']['enabled'] else '停用'}")
    print(f"  模型：{status['cloud']['model']}")
