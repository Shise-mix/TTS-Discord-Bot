@echo off
cd /d %~dp0
title Bot Installer Setup

echo ========================================================
echo  TTS-DiscordBot 環境構築インストーラー
echo ========================================================
echo.
echo  このスクリプトは、Botの動作に必要な仮想環境の作成、
echo  ライブラリのインストール、およびRust拡張のビルドを自動で行います。
echo.

REM --- Step 1: Python Check ---
echo  [ステップ 1/4] Pythonの確認中...
where python >nul 2>nul
if %errorlevel% neq 0 goto :ERROR_PYTHON
echo  - Pythonを確認しました。
echo.

REM --- Step 2: Rust Check ---
echo  [ステップ 2/4] Rust(Cargo)の確認中...
where cargo >nul 2>nul
if %errorlevel% neq 0 goto :ERROR_RUST
echo  - Rustを確認しました。
echo.

REM --- Step 3: Venv Creation ---
echo  [ステップ 3/4] 仮想環境(.venv)を作成しています...
if exist .venv goto :SKIP_VENV_CREATE

python -m venv .venv
if %errorlevel% neq 0 goto :ERROR_VENV
echo  - 仮想環境を作成しました。
goto :NEXT_STEP

:SKIP_VENV_CREATE
echo  - 既存の仮想環境を使用します。

:NEXT_STEP
echo.

REM --- Step 4: Install & Build ---
echo  [ステップ 4/4] ライブラリのインストールとRust拡張のビルド...
echo  ※ 初回はコンパイルに数分かかる場合があります。

call .venv\Scripts\activate

python -m pip install --upgrade pip >nul 2>&1
echo  - pipパッケージをインストール中...
pip install -r requirements.txt
if %errorlevel% neq 0 goto :ERROR_PIP

echo  - Rust拡張モジュール(rust_core)をビルド中...
maturin develop -m rust_core/Cargo.toml --release
if %errorlevel% neq 0 goto :ERROR_MATURIN

echo.
echo ========================================================
echo  すべてのセットアップが正常に完了しました。
echo ========================================================
echo.
echo  [次の操作]
echo  1. フォルダ内の「.env」ファイルを開き、Token等の設定を行ってください。
echo  2. 「start.bat」を実行してBotを起動してください。
echo.
pause
exit /b

REM --- エラー処理ルーチン ---

:ERROR_PYTHON
echo.
echo  [エラー] Pythonが見つかりません。
echo  ---------------------------------------------------
echo  Python公式サイトから Python 3.10以上 をインストールし、
echo  インストーラーの「Add Python to PATH」にチェックを
echo  入れてから再度実行してください。
echo  ---------------------------------------------------
pause
exit /b

:ERROR_RUST
echo.
echo  [エラー] Rust (Cargo) が見つかりません。
echo  ---------------------------------------------------
echo  高速化モジュール(rust_core)のビルドにRustが必要です。
echo  公式サイト(https://rustup.rs/)からインストールしてください。
echo  インストール後、PCを再起動してから再度実行してください。
echo  ---------------------------------------------------
pause
exit /b

:ERROR_VENV
echo.
echo  [エラー] 仮想環境の作成に失敗しました。
pause
exit /b

:ERROR_PIP
echo.
echo  [エラー] pipインストールに失敗しました。
pause
exit /b

:ERROR_MATURIN
echo.
echo  ---------------------------------------------------
echo  [エラー] Rust拡張のビルドに失敗しました。
echo  エラーログを確認してください。
echo  ---------------------------------------------------
pause
exit /b