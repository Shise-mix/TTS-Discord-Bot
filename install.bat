@echo off
cd /d %~dp0
title Bot Installer Setup

echo ========================================================
echo  TTS-DiscordBot 環境構築インストーラー
echo ========================================================
echo.

REM --- Step 1: UV Check & Install ---
echo  [ステップ 1/4] ツール(uv)の確認中...
python -m uv --version >nul 2>nul
if %errorlevel% equ 0 (
    echo  - uv は正常に動作しています。
    goto :VENV_CREATE
)

echo  - uv が見つからない、またはパスが通っていません。
echo  - インストールを試みます...
pip install uv
if %errorlevel% neq 0 (
    echo [エラー] uvのインストールに失敗しました。
    pause
    exit /b
)

REM --- Step 2: Venv Creation (Python 3.11) ---
:VENV_CREATE
echo.
echo  [ステップ 2/4] Python 3.11 仮想環境を作成しています...

if exist .venv (
    echo  - 既存の仮想環境をクリーンアップしています...
    rmdir /s /q .venv
)

echo  ※ 初回はPython 3.11のダウンロードが行われる場合があります。

REM '--seed' オプションを使用し、仮想環境作成時にpipをインストールする
python -m uv venv .venv --python 3.11 --seed
if %errorlevel% neq 0 (
    echo [エラー] 仮想環境の作成に失敗しました。
    pause
    exit /b
)

REM --- Step 3: Install Libraries ---
echo.
echo  [ステップ 3/4] ライブラリをインストールしています...

REM 仮想環境の外側からインストールを実行
python -m uv pip install -r requirements.txt --python .venv
if %errorlevel% neq 0 (
    echo [エラー] ライブラリのインストールに失敗しました。
    pause
    exit /b
)

REM --- Step 4: Build Rust ---
echo.
echo  [ステップ 4/4] Rust拡張モジュールをビルドしています...
where cargo >nul 2>nul
if %errorlevel% neq 0 (
    echo [エラー] Rust ^(cargo^) が見つかりません。Rustをインストールしてください。
    pause
    exit /b
)

REM pipが存在するため標準モードで実行
.venv\Scripts\maturin develop -m rust_core/Cargo.toml --release
if %errorlevel% neq 0 (
    echo [エラー] Rust拡張のビルドに失敗しました。
    pause
    exit /b
)

echo.
echo ========================================================
echo  セットアップ完了！
echo  何かキーを押すと終了します。
echo ========================================================
echo.
pause