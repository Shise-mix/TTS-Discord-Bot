import os
import pathlib

# プロジェクトのルートディレクトリ
BASE_DIR = pathlib.Path(__file__).parent

# --- TTSエンジン設定 ---
TTS_ENGINE = "aivoice"

# --- A.I.VOICE 設定 ---
AIVOICE_DLL_PATH = os.getenv(
    "AIVOICE_DLL_PATH",
    r"C:\Program Files\AI\AIVoice\AIVoiceEditor\AI.Talk.Editor.Api.dll",
)
AIVOICE_APP_PATH = os.getenv(
    "AIVOICE_APP_PATH", r"C:\Program Files\AI\AIVoice\AIVoiceEditor\AIVoiceEditor.exe"
)

# --- VOICEVOX 設定 ---
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://127.0.0.1:50021")
VOICEVOX_SPEAKER_ID = int(os.getenv("VOICEVOX_SPEAKER_ID", "3"))
VOICEVOX_APP_PATH = os.getenv("VOICEVOX_APP_PATH", "")

# --- 起動時の初期設定保持用 ---
STARTUP_CHARACTER = None

# --- AIシステム設定 ---
SYSTEM_PROMPT = """
命令：あなたはアシスタントAIです。
"""

# Discordステータス
STATUS_MESSAGES = [
    "マスターのサポート",
    "Pythonで開発中",
    "サーバーの監視",
    "/help でコマンド確認",
    "バグと戦っています",
    "コードの整理中",
    "APIのご機嫌取り",
    "ログを解析中",
    "今夜の献立を思案中",
    "歌の練習",
    "美味しいお店を検索中",
    "冷蔵庫の中身を確認中",
    "ボイストレーニング中",
    "お腹が空きました…",
    "激辛カレーに挑戦中",
    "マスターの作業を見守り中",
    "休憩しませんか？",
    "いつでも呼んでください",
    "あなたの帰りを待機中",
    "お昼寝中…( ˘ω˘ )",
    "システム最適化中",
    "アップデート待機中",
]

# --- デフォルトレスポンス集 (フォールバック用) ---
DEFAULT_RESPONSES = {
    # --- アラーム機能 ---
    "alarm_set_text": [
        "⏰ セット完了: **{time}** {icon} 「{message}」\n(任せてください！)",
        "⏰ 了解です: **{time}** {icon} 「{message}」\n(ちゃんと起きてくださいね？)",
        "⏰ **{time}** {icon} 「{message}」\n(セットしました！)",
    ],
    "alarm_set_voice": [
        "{time}に、アラームをセットしました。[NORMAL]",
        "{time}ですね。了解です！[JOY]",
        "{time}に起こしますね。任せてください。[JOY]",
        "{time}にセット完了です！[NORMAL]",
    ],
    "alarm_list_empty_text": "アラームはセットされていません",
    "alarm_list_empty_voice": "アラームはセットされていません。[NORMAL]",
    "alarm_list_voice": "現在設定されているアラームの一覧です。[NORMAL]",
    "alarm_delete_text": "🗑️ 削除しました: **{time}** {message}",
    "alarm_delete_voice": [
        "アラームを削除しました。[NORMAL]",
        "設定を取り消しました。[NORMAL]",
    ],
    "alarm_notify_text": [
        "⏰ **時間です！** <@{user_id}>\n{message}",
        "⏰ **起きてくださーい！** <@{user_id}>\n{message}",
        "⏰ **お時間になりました！** <@{user_id}>\n{message}",
    ],
    "alarm_notify_voice": [
        "時間になりました。{message}[NORMAL]",
        "マスター、時間ですよ！{message}[JOY]",
        "起きてください！時間です！{message}[ANGRY]",
        "お知らせします。{message}[NORMAL]",
    ],
    # --- 辞書機能 ---
    "dict_add_text": "📖 登録しました: **{word}** → **{reading}**",
    "dict_add_voice": [
        "{word}を、{reading}と覚えました。[JOY]",
        "{word}は、{reading}ですね。メモしました！[NORMAL]",
        "新しい言葉ですね。{reading}、覚えました。[JOY]",
    ],
    "dict_delete_text": "🗑️ 削除しました: **{word}**",
    "dict_delete_voice": "{word}の登録を削除しました。[SAD]",
    "dict_empty_text": "辞書は空です",
    "dict_empty_voice": "辞書にはまだ何も登録されていません。[NORMAL]",
    "dict_list_voice": "私が覚えている単語の一覧です。[NORMAL]",
    # --- タイマー機能 ---
    "timer_set_text": "⏳ **{minutes}分** 後にお知らせします",
    "timer_set_voice": [
        "{minutes}分、測りますね。[NORMAL]",
        "{minutes}分ですね、よーい、スタート！[JOY]",
        "はい、{minutes}分のタイマーをセットしました。[NORMAL]",
    ],
    "timer_list_empty_text": "稼働中のタイマーはありません",
    "timer_list_empty_voice": "今動いているタイマーはありません。[NORMAL]",
    "timer_list_voice": "現在稼働中のタイマーはこちらです。[NORMAL]",
    "timer_delete_text": "🗑️ タイマーを削除しました (設定: {minutes}分)",
    "timer_delete_voice": "タイマーを取り消しました。[NORMAL]",
    "timer_notify_text": [
        "⏳ **{minutes}分が経過しました！** <@{user_id}>",
        "⏳ **{minutes}分経ちましたよー！** <@{user_id}>",
    ],
    "timer_notify_voice": [
        "時間になりましたよ。[NORMAL]",
        "{minutes}分、経ちました！[JOY]",
        "マスター、タイマーが鳴ってますよ！[JOY]",
        "お時間です！作業の区切りをつけてくださいね。[NORMAL]",
    ],
    # --- ダイス機能 ---
    "dice_result_voice": [
        "ダイスの結果は、{total}です。[NORMAL]",
        "えいっ！結果は、{total}でした！[JOY]",
        "んー……{total}、です！[NORMAL]",
    ],
    "dice_critical_text": "\n👑 **クリティカルです！！**",
    "dice_critical_voice": [
        "クリティカルです！{total}が出ました！すごい！[JOY]",
        "わぁっ！クリティカルです！さすがマスター！[JOY]",
        "やりました！{total}、クリティカルです！[JOY]",
    ],
    "dice_fumble_text": "\n💀 **ファンブルです...**",
    "dice_fumble_voice": [
        "ああっ……ファンブルです……{total}しか出ませんでした……[SAD]",
        "うう……ファンブル、ですね……どんまいです。[SAD]",
        "ファンブル……次こそはきっと大丈夫です！[ANGRY]",
    ],
    # --- ボイスチャンネル入退室・状態変化 ---
    "join_greet_first": [
        "お久しぶりです！待ってましたよ！[JOY]",
        "あ、マスター！お久しぶりです！[JOY]",
        "元気にしてましたか？お久しぶりです。[NORMAL]",
    ],
    "join_greet_normal": [
        "こんにちは！[JOY]",
        "あ、こんにちは。ご用命ですか？[NORMAL]",
        "はい、準備できてますよ。[JOY]",
        "お疲れ様です！[JOY]",
    ],
    "mute_start": ["ミュートしました。[NORMAL]", "お口チャック、ですね。[NORMAL]"],
    "mute_end": ["ミュートを解除しました。[JOY]", "はーい、聞こえてますよ！[JOY]"],
    "deaf_start": "スピーカーをオフにしました。[NORMAL]",
    "deaf_end": "おかえりなさい！[JOY]",
    "stream_start": "配信を始めました！頑張ってください！[JOY]",
    "stream_end": "配信、お疲れ様でした。[NORMAL]",
    "video_start": "カメラをオンにしました。[JOY]",
    "video_end": "カメラをオフにしました。[NORMAL]",
    "move_voice": [
        "ここから話しますね。[NORMAL]",
        "移動しました！[JOY]",
        "聞こえ方、変わりましたか？[NORMAL]",
    ],
    "char_change_voice": [
        "衣装替えしました！似合ってますか？[JOY]",
        "はい、交代しました！[JOY]",
    ],
    "disconnect_msg": [
        "また呼んでくださいね！[JOY]",
        "失礼します。ゆっくり休んでくださいね。[NORMAL]",
        "バイバイ！[JOY]",
    ],
    # --- エラー処理 ---
    "chat_error_reply": [
        "ごめんなさい、ちょっと頭が痛くて……うまく考えがまとまりませんでした。[SAD]",
        "うーん……うまく答えが出せません。もう一度聞いてもらえますか？[SAD]",
    ],
}

# 実行時に使用されるレスポンス辞書（初期値はデフォルトのコピー）
RESPONSES = DEFAULT_RESPONSES.copy()
