import discord
from discord.ext import commands, tasks
import os
import asyncio
import logging
import random
import pathlib
import time
import subprocess
import json
from dotenv import load_dotenv

# 設定ファイルの読み込み
load_dotenv()
import settings  # noqa: E402
from cogs.tts_engines import get_tts_provider  # noqa: E402

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 環境変数からトークンを取得
TOKEN = os.getenv("DISCORD_TOKEN")


def input_index(prompt, options, zero_label=None):
    """
    コンソールに一覧を表示し、ユーザーにインデックス番号を選択させる関数。
    """
    print(f"\n{prompt}")

    start_num = 0 if zero_label else 1

    if zero_label:
        print(f"  [0] {zero_label}")

    for i, opt in enumerate(options):
        print(f"  [{i + 1}] {opt}")

    while True:
        val = input(f"番号を入力してください ({start_num}-{len(options)}) > ")
        if not val.isdigit():
            continue
        idx = int(val)

        if idx == 0 and zero_label:
            return None

        if 1 <= idx <= len(options):
            return options[idx - 1]


def select_character_interactive(presets):
    """
    プリセットリストを解析し、キャラクターごとにグループ化して選択させる関数
    """
    groups = {}
    for p in presets:
        if "(" in p:
            name = p.split("(")[0]
        elif "（" in p:
            name = p.split("（")[0]
        else:
            name = p

        if name not in groups:
            groups[name] = []
        groups[name].append(p)

    group_names = list(groups.keys())

    print(f"\n使用するキャラクターを選んでください (全{len(group_names)}名):")
    for i, name in enumerate(group_names):
        count = len(groups[name])
        suffix = f" ({count}種)" if count > 1 else ""
        print(f"  [{i + 1}] {name}{suffix}")

    while True:
        val = input(f"キャラクター番号を入力 (1-{len(group_names)}) > ").strip()
        if not val.isdigit():
            continue
        idx = int(val)
        if 1 <= idx <= len(group_names):
            selected_name = group_names[idx - 1]
            break

    variants = groups[selected_name]
    if len(variants) == 1:
        return variants[0]

    print(f"\n{selected_name} のスタイルを選択:")
    for i, v in enumerate(variants):
        display_style = v
        if selected_name in v:
            display_style = v.replace(selected_name, "").strip("()（）")
            if not display_style:
                display_style = "標準"

        print(f"  [{i + 1}] {display_style}")

    while True:
        val = input(f"スタイル番号を入力 (1-{len(variants)}) > ").strip()
        if not val.isdigit():
            continue
        idx = int(val)
        if 1 <= idx <= len(variants):
            return variants[idx - 1]


def try_launch_app(engine_name):
    """
    指定されたエンジンのアプリケーションを自動起動する。
    """
    app_path = None

    if engine_name == "aivoice":
        app_path = getattr(settings, "AIVOICE_APP_PATH", None)
    elif engine_name == "voicevox":
        app_path = getattr(settings, "VOICEVOX_APP_PATH", None)

    if app_path and os.path.exists(app_path):
        try:
            print(f"アプリを起動しています (バックグラウンド): {app_path}")

            startup_kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }

            if os.name == "nt":
                info = subprocess.STARTUPINFO()
                info.dwFlags |= 1
                info.wShowWindow = 7
                startup_kwargs["startupinfo"] = info

            subprocess.Popen(app_path, **startup_kwargs)

        except Exception as e:
            logger.error(f"アプリの自動起動に失敗しました: {e}")
            print("! 自動起動に失敗しました。手動でアプリを起動してください。")


def wait_for_launch(provider, max_retries=60):
    print("エンジンの起動を確認中", end="", flush=True)
    for _ in range(max_retries):
        try:
            provider.initialize()
            presets = provider.get_presets()
            if presets:
                print(" 完了！")
                return presets
        except Exception:
            pass
        time.sleep(1)
        print(".", end="", flush=True)

    print("\nタイムアウト: エンジンの起動が確認できませんでした。")
    return []


def load_character_config(char_dir: pathlib.Path):
    """
    指定されたキャラクターフォルダ内の設定ファイルを読み込む。
    - *.txt -> settings.SYSTEM_PROMPT
    - *.json -> settings.RESPONSES (マージ)
    """
    # 初期化
    settings.RESPONSES = settings.DEFAULT_RESPONSES.copy()
    settings.SYSTEM_PROMPT = None

    # フォルダ内のファイルを走査
    txt_file = None
    json_file = None

    for f in char_dir.glob("*"):
        if f.suffix == ".txt" and txt_file is None:
            txt_file = f
        elif f.suffix == ".json" and json_file is None:
            json_file = f

    # プロンプト読み込み
    if txt_file:
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                settings.SYSTEM_PROMPT = f.read()
            logger.info(f"Loaded prompt from: {txt_file.name}")
        except Exception as e:
            logger.error(f"Failed to load prompt: {e}")
    else:
        logger.warning(f"No .txt prompt found in {char_dir.name}")

    # セリフ集読み込み
    if json_file:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                custom_responses = json.load(f)
            settings.RESPONSES.update(custom_responses)
            logger.info(f"Loaded responses from: {json_file.name}")
        except Exception as e:
            logger.error(f"Failed to load json responses: {e}")

    return bool(txt_file)


class TTSBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        prefix = getattr(settings, "COMMAND_PREFIX", "!")

        super().__init__(command_prefix=prefix, intents=intents, help_command=None)

    async def setup_hook(self):
        initial_extensions = ["cogs.audio", "cogs.chat", "cogs.utils"]

        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension} ......成功")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")

        try:
            await self.tree.sync()
            logger.info("Synced commands (Global) ......成功")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Engine: {settings.TTS_ENGINE}")
        logger.info(f"Character: {settings.STARTUP_CHARACTER}")
        logger.info("System Ready.")

        if not self.change_status_loop.is_running():
            self.change_status_loop.start()

    @tasks.loop(minutes=10)
    async def change_status_loop(self):
        status_list = getattr(settings, "STATUS_MESSAGES", ["Running..."])
        await self.change_presence(
            activity=discord.Game(name=random.choice(status_list))
        )

    @change_status_loop.before_loop
    async def before_status_loop(self):
        await self.wait_until_ready()


async def main():
    print("=== 起動設定ウィザード ===")

    # 1. TTSエンジンの選択
    engines = ["A.I.VOICE", "VOICEVOX"]
    selected_engine = input_index("使用するTTSエンジンを選択してください:", engines)

    if selected_engine == "A.I.VOICE":
        settings.TTS_ENGINE = "aivoice"
    elif selected_engine == "VOICEVOX":
        settings.TTS_ENGINE = "voicevox"
    else:
        settings.TTS_ENGINE = "aivoice"

    print(f"-> エンジン: {settings.TTS_ENGINE} を選択しました。")

    # アプリの自動起動処理
    try_launch_app(settings.TTS_ENGINE)

    # 2. キャラクター選択
    engine_name = settings.TTS_ENGINE
    temp_provider = get_tts_provider(engine_name)

    presets = wait_for_launch(temp_provider)

    if presets:
        char_choice = select_character_interactive(presets)

        if char_choice:
            settings.STARTUP_CHARACTER = char_choice
            print(f"-> キャラクター: {char_choice} を選択しました。")
    else:
        print("! プリセットが見つかりませんでした。")

    # 3. 人格(charactersフォルダ)選択
    # 修正: charactersフォルダ内のディレクトリを一覧表示する
    char_base_dir = pathlib.Path("characters")
    char_dirs = []

    if char_base_dir.exists():
        # ディレクトリかつ中身があるものを抽出
        char_dirs = [d for d in char_base_dir.iterdir() if d.is_dir()]

    if char_dirs:
        # フォルダ名でソートして表示
        char_names = sorted([d.name for d in char_dirs])

        selected_char_name = input_index(
            "使用する人格設定(characters)を選択してください:",
            char_names,
            zero_label="LLMを使用しない (No Use)",
        )

        if selected_char_name:
            target_dir = char_base_dir / selected_char_name
            print(f"-> 設定フォルダ: {selected_char_name} を読み込みます...")

            if load_character_config(target_dir):
                print("-> 完了しました。")
            else:
                print("-> 注意: プロンプトファイルが見つかりませんでした。")
    else:
        print(
            "\n※ charactersフォルダにキャラクター設定が見つかりません。LLM機能はオフで起動します。"
        )
        settings.SYSTEM_PROMPT = None

    # Bot起動
    print("\nBotを起動しています...")
    async with TTSBot() as bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        if os.name == "nt":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
