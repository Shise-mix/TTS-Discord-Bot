# TTS Discord Bot (A.I.VOICE & VOICEVOX + LLM)

A.I.VOICE Editor および VOICEVOX と連携する Discord 読み上げ Bot です。
音声処理のバックエンドに Rust を使用することで、低遅延な加工処理を実現しています。

---

## 主な機能

### 1. TTS エンジン連携
* **A.I.VOICE**: Editor を介した音声合成。プリセットによる感情表現の切り替えに対応。
* **VOICEVOX**: API 経由での音声合成。ピッチや抑揚の動的な操作が可能。

### 2. Rust による音声処理
無音カット、ゲイン調整、リバーブ、PCM 変換などの処理を Rust (`rust_core`) で実装しています。
オンメモリで処理を行うことで、ディスク I/O を抑制し、レスポンス速度を向上させています。

### 3. キャラクター管理
`characters/` ディレクトリ内でキャラクターごとの設定を管理します。
* **人格設定**: LLM に渡すシステムプロンプト。
* **セリフ設定**: システム音声（参加、切断、時報など）の個別上書き。

### 4. システム設計
* **データバリデーション**: Pydantic を使用し、設定ファイルの不整合を起動時に検知します。
* **非同期処理**: discord.py のイベントループを妨げない設計により、Bot の応答性を確保しています。

### 5. LLM 連携・ユーティリティ
* **対話機能**: LM Studio 等の API と連携し、文脈に応じた返答と感情表現を行います。
* **実用機能**: アラーム、タイマー、辞書登録、ダイスロール。

---

## 動作環境

* **OS**: Windows 10 / 11 (64bit)
* **Python**: 3.10 以上
* **Rust**: 1.70 以上 (ビルドに必要)
* **TTS**: A.I.VOICE Editor (Ver.1 / 2) または VOICEVOX

---

## セットアップ

### 1. Rust の導入
[Rust 公式サイト](https://www.rust-lang.org/tools/install) から `rustup-init.exe` を取得し、デフォルト設定でインストールしてください。

### 2. リポジトリの取得
```bash
git clone https://github.com/Shise-mix/TTS-Discord-Bot.git
cd TTS-DiscordBot
```

### 3. 依存関係の構築
`install.bat` を実行してください。
以下の処理が自動で行われます。
1. パッケージマネージャ `uv` のインストール
2. Python 3.11 仮想環境の作成
3. 依存ライブラリのインストール
4. Rust モジュールのビルド

### 4. 設定ファイルの編集
`.env.example` を `.env` にリネームし、トークンおよびパスを設定してください。

```properties
DISCORD_TOKEN=your_token_here
LLM_API_KEY=lm-studio
AIVOICE_DLL_PATH=C:\Program Files\AI\AIVoice\AIVoiceEditor\AI.Talk.Editor.Api.dll
AIVOICE_APP_PATH=C:\Program Files\AI\AIVoice\AIVoiceEditor\AIVoiceEditor.exe
VOICEVOX_URL=http://127.0.0.1:50021
VOICEVOX_APP_PATH=C:\Users\Username\AppData\Local\Programs\VOICEVOX\VOICEVOX.exe
```

---

## キャラクター設定

`characters/` 内の各フォルダでプロンプトとレスポンスを定義します。

### 1. プロンプト (*.txt)
LLM の振る舞いを記述します。

### 2. レスポンス (*.json)
システムメッセージを定義します。
```json
{
    "join_greet_first": [
        "やっほー！[JOY]",
        "待ってたよ。[NORMAL]"
    ]
}
```

---

## エンジンの事前準備

### A.I.VOICE の場合
感情表現を有効にするため、Editor 上で以下の命名規則に従ってプリセットを作成してください。
Bot はこのサフィックスを見て感情を切り替えます。

| 感情タグ | プリセット名 (例: 紲星 あかり) | パラメータの目安 |
|---|---|---|
| **[NORMAL]** | `紲星 あかり_NORMAL` | 標準 |
| **[JOY]** | `紲星 あかり_JOY` | 抑揚高め、速度やや速め |
| **[SAD]** | `紲星 あかり_SAD` | 抑揚低め、速度遅め |
| **[ANGRY]** | `紲星 あかり_ANGRY` | 音量大きめ、速度速め |
| **[SURPRISE]** | `紲星 あかり_SURPRISE` | 語尾上がり |

### VOICEVOX の場合
事前のプリセット作成は不要です。
起動ウィザードにて、キャラクターとスタイル（ノーマル、あまあま等）を選択するだけで使用可能です。

---

## 使用方法

### 1. 起動
`start.bat` を実行してください。
ウィザード形式でエンジン、キャラクター、人格設定を選択して起動します。

### 2. 主要コマンド

| コマンド | 内容 |
|---|---|
| `/join` | VC 参加 |
| `/bye` | VC 切断 |
| `/char` | キャラクター変更 |
| `/stop` | 再生停止・キュー消去 |
| `/dict add` | 辞書登録 |

### 3. AI 対話
Bot へのメンション、または返信によって LLM との会話が可能です。

---

## ライセンス
MIT License

※ 本ソフトウェアは非公式ツールです。株式会社AI および VOICEVOX とは一切関係ありません。
各音声合成エンジンの利用規約（EULA）およびキャラクター利用ガイドラインを遵守してご利用ください。

---

## フォーマット
```bash
ruff format
ruff check --fix
```