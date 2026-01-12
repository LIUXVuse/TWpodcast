@echo off
REM ===============================================
REM Windows Whisper 定時執行腳本
REM ===============================================
REM
REM 功能：檢查 input 資料夾是否有檔案，有的話執行 Whisper
REM
REM 使用方式：設定 Task Scheduler 定時執行此腳本
REM
REM ===============================================

cd /d "%~dp0"

echo ============================================
echo 🎙️ Whisper 轉錄腳本
echo ============================================
echo.
echo 📂 檢查 input 資料夾...

REM 檢查 input 資料夾是否有 mp3 檔案
set "hasFiles=0"
for %%f in (input\*.mp3) do (
    set "hasFiles=1"
    echo 🆕 發現：%%~nxf
)

if "%hasFiles%"=="0" (
    echo ✅ 沒有新檔案需要處理
    echo.
    goto :end
)

echo.
echo 🚀 開始 Whisper 轉錄...
echo.

REM 執行 Whisper
call run_all_whisper_cuda.bat

echo.
echo ✅ 轉錄完成！
echo.

:end
echo 🕐 %date% %time%
echo ============================================

REM 等待 3 秒讓用戶看到結果（如果手動執行）
timeout /t 3 /nobreak >nul
