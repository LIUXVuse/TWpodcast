# ===============================================
# Windows Whisper 自動監控腳本
# ===============================================
#
# 功能：監控 input 資料夾，有新音檔時自動執行 Whisper 轉錄
#
# 使用方式：
#   1. 將此檔案放到 whisper.cpp 目錄
#   2. 右鍵 → 使用 PowerShell 執行
#
# 或設定開機自動執行：
#   1. Win+R → taskschd.msc
#   2. 建立基本工作 → 登入時觸發
#   3. 動作：啟動程式 powershell.exe
#   4. 引數：-ExecutionPolicy Bypass -File "C:\path\to\watch_and_transcribe.ps1"
# ===============================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InputDir = Join-Path $ScriptDir "input"
$WhisperBat = Join-Path $ScriptDir "run_all_whisper_cuda.bat"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🎙️ Whisper 自動監控腳本" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📂 監控目錄：$InputDir"
Write-Host "🔧 Whisper 腳本：$WhisperBat"
Write-Host ""
Write-Host "⏳ 等待新音檔... (按 Ctrl+C 停止)" -ForegroundColor Yellow
Write-Host ""

# 建立 FileSystemWatcher
$Watcher = New-Object System.IO.FileSystemWatcher
$Watcher.Path = $InputDir
$Watcher.Filter = "*.mp3"
$Watcher.IncludeSubdirectories = $false
$Watcher.EnableRaisingEvents = $true

# 記錄已處理的檔案
$ProcessedFiles = @{}

# 處理新檔案的函數
$Action = {
    $FilePath = $Event.SourceEventArgs.FullPath
    $FileName = $Event.SourceEventArgs.Name
    $ChangeType = $Event.SourceEventArgs.ChangeType
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    # 等待檔案寫入完成
    Start-Sleep -Seconds 3
    
    # 檢查檔案是否還在被寫入
    $Retries = 0
    while ($Retries -lt 10) {
        try {
            $File = [System.IO.File]::Open($FilePath, 'Open', 'Read', 'None')
            $File.Close()
            break
        } catch {
            $Retries++
            Start-Sleep -Seconds 2
        }
    }
    
    Write-Host ""
    Write-Host "[$TimeStamp] 🆕 新檔案：$FileName" -ForegroundColor Green
    Write-Host "[$TimeStamp] 🚀 開始 Whisper 轉錄..." -ForegroundColor Cyan
    
    # 執行 Whisper
    $Process = Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$($Event.MessageData.WhisperBat)`"" -Wait -PassThru -NoNewWindow
    
    if ($Process.ExitCode -eq 0) {
        Write-Host "[$TimeStamp] ✅ 轉錄完成！" -ForegroundColor Green
    } else {
        Write-Host "[$TimeStamp] ❌ 轉錄失敗 (ExitCode: $($Process.ExitCode))" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "⏳ 繼續等待新音檔..." -ForegroundColor Yellow
}

# 註冊事件
$MessageData = New-Object PSObject -Property @{
    WhisperBat = $WhisperBat
}

Register-ObjectEvent -InputObject $Watcher -EventName "Created" -Action $Action -MessageData $MessageData | Out-Null

# 保持腳本運行
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    # 清理
    Unregister-Event -SourceIdentifier $Watcher.Id -ErrorAction SilentlyContinue
    $Watcher.EnableRaisingEvents = $false
    $Watcher.Dispose()
    Write-Host "`n👋 監控已停止" -ForegroundColor Yellow
}
