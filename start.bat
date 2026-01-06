@echo off
cd /d %~dp0
title TTS-DiscordBot Launcher

echo ===================================================
echo  TTS-DiscordBot 起動
echo ===================================================
echo.

rem 仮想環境のチェック
if not exist ".venv\Scripts\python.exe" (
    echo [エラー] .venv が見つかりません。
    echo install.bat を実行して環境を構築してください。
    pause
    exit /b
)

rem Python実行直前に文字コードをUTF-8に変更 (ログの絵文字対策)
chcp 65001 > nul

rem Botの実行
".venv\Scripts\python.exe" main.py

rem Botが終了またはクラッシュした際に画面を閉じないようにする
pause