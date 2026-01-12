#!/usr/bin/env python3
"""
🚀 Git Publisher - 自動推送摘要到 GitHub

功能：
- 當新摘要生成後，自動 commit 並 push 到 GitHub
- 支援設定開關 (config/services.yaml 中的 git_publish)
"""

import subprocess
from pathlib import Path
from typing import Optional
import yaml


class GitPublisher:
    """自動 Git 推送器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path(__file__).parent.parent / 'config'
        self.repo_path = Path(__file__).parent.parent  # 專案根目錄
        self._load_config()
    
    def _load_config(self):
        """載入設定"""
        services_file = self.config_path / 'services.yaml'
        if services_file.exists():
            with open(services_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                git_config = config.get('git_publish', {})
                self.enabled = git_config.get('enabled', False)
                self.auto_commit = git_config.get('auto_commit', True)
                self.commit_message_template = git_config.get(
                    'commit_message', 
                    '📝 新增 Podcast 摘要：{episode_name}'
                )
        else:
            self.enabled = False
            self.auto_commit = True
            self.commit_message_template = '📝 新增 Podcast 摘要：{episode_name}'
    
    def _run_git(self, *args) -> tuple[bool, str]:
        """執行 git 命令"""
        try:
            result = subprocess.run(
                ['git'] + list(args),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            return success, output.strip()
        except Exception as e:
            return False, str(e)
    
    def publish(self, episode_name: str, summary_path: Optional[Path] = None) -> dict:
        """
        推送新摘要到 GitHub
        
        Args:
            episode_name: 集數名稱（用於 commit message）
            summary_path: 摘要檔案路徑（可選，用於精確 add）
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        if not self.enabled:
            return {'success': False, 'message': 'Git 自動發布已停用'}
        
        # 1. Add files
        if summary_path and summary_path.exists():
            # 只 add 該摘要檔案
            relative_path = summary_path.relative_to(self.repo_path)
            success, output = self._run_git('add', str(relative_path))
        else:
            # Add all summaries
            success, output = self._run_git('add', 'data/summaries/')
        
        if not success:
            return {'success': False, 'message': f'Git add 失敗: {output}'}
        
        # 2. Check if there are changes to commit
        success, output = self._run_git('diff', '--cached', '--quiet')
        if success:
            # No changes staged
            return {'success': True, 'message': '沒有新的變更需要提交'}
        
        # 3. Commit
        commit_msg = self.commit_message_template.format(episode_name=episode_name)
        success, output = self._run_git('commit', '-m', commit_msg)
        if not success:
            return {'success': False, 'message': f'Git commit 失敗: {output}'}
        
        # 4. Push
        success, output = self._run_git('push')
        if not success:
            return {'success': False, 'message': f'Git push 失敗: {output}'}
        
        return {'success': True, 'message': f'已推送：{commit_msg}'}
    
    def get_status(self) -> dict:
        """取得 Git 狀態"""
        success, branch = self._run_git('branch', '--show-current')
        if not success:
            return {'connected': False, 'error': 'Not a git repository'}
        
        success, remote = self._run_git('remote', 'get-url', 'origin')
        
        return {
            'enabled': self.enabled,
            'connected': True,
            'branch': branch,
            'remote': remote if success else 'No remote'
        }


# 測試用
if __name__ == "__main__":
    publisher = GitPublisher()
    print("📊 Git Publisher 狀態：")
    print(publisher.get_status())
