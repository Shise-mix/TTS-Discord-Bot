import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import logging
import traceback
import io
import random
import settings
from .consts import load_json, extract_emotion
from .models import CharacterResponses
from .tts_engines import get_tts_provider

# Rust拡張モジュールのインポート
try:
    import rust_core
except ImportError:
    print("[CRITICAL] 'rust_core' module not found.")
    rust_core = None

logger = logging.getLogger(__name__)


class RustAudioSource(discord.AudioSource):
    """メモリ上のPCMデータを再生するAudioSource"""

    def __init__(self, pcm_data: bytes):
        self.stream = io.BytesIO(pcm_data)

    def read(self):
        return self.stream.read(3840)

    def is_opus(self):
        return False


class AudioSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.speech_queue = asyncio.Queue()

        engine_name = getattr(settings, "TTS_ENGINE", "aivoice")
        self.tts_provider = get_tts_provider(engine_name)
        self.tts_provider.initialize()

        start_char = getattr(settings, "STARTUP_CHARACTER", None)
        if start_char:
            logger.info(f"Applying startup character: {start_char}")
            self.tts_provider.set_preset(start_char)

        # Pydanticモデルとしてロード
        # settings.RESPONSES は辞書だが、型安全なアクセスのために変換を試みる
        # (charactersフォルダからのロード機能と統合するため、settings.RESPONSESをソースとする)
        try:
            self.responses = CharacterResponses.parse_obj(settings.RESPONSES)
        except Exception:
            logger.warning(
                "Failed to parse RESPONSES into Pydantic model. Using default."
            )
            self.responses = CharacterResponses()

        self.word_dict = load_json("dictionary.json", {})
        self.bg_task = self.bot.loop.create_task(self.process_queue())

    def cog_unload(self):
        self.bg_task.cancel()
        if self.tts_provider:
            self.tts_provider.terminate()

    def update_responses(self, new_responses_dict: dict):
        """キャラクター変更時にレスポンス定義を更新する"""
        try:
            self.responses = CharacterResponses.parse_obj(new_responses_dict)
            logger.info("AudioSystem responses updated.")
        except Exception as e:
            logger.error(f"Failed to update responses: {e}")

    async def process_queue(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                # キューからタスク取得
                task = await self.speech_queue.get()

                try:
                    vc_client, text, emotion = task

                    if vc_client and vc_client.is_connected():
                        # 重い処理を別スレッドへ逃がす (非同期化)
                        audio_source = await self.bot.loop.run_in_executor(
                            None, self._generate_audio_sync, text, emotion
                        )

                        if audio_source:
                            await self.play_audio_source(vc_client, audio_source)

                except Exception as e:
                    logger.error(f"Task processing error: {e}")
                    logger.error(traceback.format_exc())
                finally:
                    # 成功・失敗に関わらず必ず完了通知を送る
                    self.speech_queue.task_done()

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # キュー取得自体（get）のエラーなど
                logger.error(f"Queue get error: {e}")

    def _generate_audio_sync(self, text: str, emotion: str):
        """
        【別スレッド実行用】
        TTS生成 -> メモリ読込 -> Rustパイプライン加工 -> AudioSource作成
        """
        if not rust_core:
            return None

        # 辞書置換
        for word, reading in self.word_dict.items():
            text = text.replace(word, reading)

        # 一時ファイルパス (A.I.VOICE用。VOICEVOXなら不要だが共通化のため使用)
        # ※ A.I.VOICEは仕様上、ファイル出力が必須。
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            temp_path = tf.name

        wav_bytes = None

        try:
            # 1. TTSエンジンでWave生成 (同期ブロック)
            self.tts_provider.generate_audio(text, emotion, temp_path)

            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                # 2. ファイルを即座にメモリに読み込んで削除
                with open(temp_path, "rb") as f:
                    wav_bytes = f.read()

                # A.I.VOICEが出力したファイルはもう不要
                os.remove(temp_path)

                # 3. Rustパイプライン処理 (オンメモリ)
                # Trim(100) -> Gain(3.0dB) -> Reverb(50ms, 0.3, 0.15)
                # パラメータは必要に応じて設定ファイルから読み込む形にしても良い
                pcm_data = rust_core.process_audio_pipeline(
                    wav_bytes,
                    3.0,  # Gain dB
                    100,  # Silence Threshold
                    True,  # Reverb Enabled
                    50,  # Delay ms
                    0.3,  # Decay
                    0.15,  # Mix
                )

                return RustAudioSource(pcm_data)
            else:
                logger.warning("TTS generation failed or empty file.")
                return None

        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            logger.error(traceback.format_exc())
            # ゴミ掃除
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return None

    async def play_audio_source(self, vc_client, audio_source):
        if not vc_client.is_connected():
            return
        try:
            vc_client.play(audio_source)
            while vc_client.is_playing():
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Playback error: {e}")

    def enqueue_speech(self, vc_client, text, emotion="JOY"):
        logger.info(f"Audio Enqueued: {text} ({emotion})")
        self.speech_queue.put_nowait((vc_client, text, emotion))

    def _get_response(self, key, **kwargs):
        """
        Pydanticモデルからレスポンスを取得する
        """
        # モデルのフィールドを取得 (リストならランダム選択、文字列ならそのまま)
        raw_val = getattr(self.responses, key, None)

        if raw_val is None:
            return None, "NORMAL"

        template = random.choice(raw_val) if isinstance(raw_val, list) else raw_val

        if not template:
            return None, "NORMAL"

        try:
            text = template.format(**kwargs)
        except Exception:
            text = template
        return extract_emotion(text)

    # --- Commands ---

    @app_commands.command(name="join", description="ボイスチャンネルに接続します")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message(
                "User is not in a voice channel.", ephemeral=True
            )
            return

        target_channel = interaction.user.voice.channel
        guild_vc = interaction.guild.voice_client

        if guild_vc and guild_vc.is_connected():
            if guild_vc.channel == target_channel:
                await interaction.response.send_message(
                    "Already connected to this channel.", ephemeral=True
                )
            else:
                await guild_vc.move_to(target_channel)
                await interaction.response.send_message("Moved to your channel.")
                text, emo = self._get_response("move_voice")
                self.enqueue_speech(guild_vc, text or "移動しました", emo)
        else:
            vc = await target_channel.connect()
            await interaction.response.send_message("Connected.")
            text, emo = self._get_response("join_greet_first")
            self.enqueue_speech(vc, text or "接続しました", emo)

    @app_commands.command(name="stop", description="読み上げ停止")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()

        # キューを空にする
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except asyncio.QueueEmpty:
                break

        await interaction.response.send_message("Stopped.")

    @app_commands.command(name="bye", description="切断")
    async def bye(self, interaction: discord.Interaction):
        # 1. 処理が長引く（再生待ちする）ことをDiscordに通知し、タイムアウトを防ぐ
        await interaction.response.defer()

        vc = interaction.guild.voice_client
        if vc:
            # ユーザーには「切断処理中」であることを先に伝える
            # defer済みなのて followup.send を使う
            await interaction.followup.send("Disconnecting...")

            text, emo = self._get_response("disconnect_msg")
            if text:
                self.enqueue_speech(vc, text, emo)

            # 2. 音声再生が完了するまで待機（ここが数秒以上かかる）
            await self.speech_queue.join()

            # 3. 再生完了後に切断
            await vc.disconnect()

            # (オプション) 完了メッセージを送る場合
            # await interaction.followup.send("Disconnected.")
        else:
            await interaction.followup.send("Not connected.", ephemeral=True)

    async def preset_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        presets = self.tts_provider.get_presets()
        return [
            app_commands.Choice(name=p, value=p)
            for p in presets
            if current.lower() in p.lower()
        ][:25]

    @app_commands.command(name="char", description="TTSキャラクター変更")
    @app_commands.autocomplete(style=preset_autocomplete)
    async def char(self, interaction: discord.Interaction, style: str):
        if self.tts_provider.set_preset(style):
            await interaction.response.send_message(f"Changed to: **{style}**")
            if interaction.guild.voice_client:
                text, emo = self._get_response("char_change_voice")
                self.enqueue_speech(
                    interaction.guild.voice_client, text or "交代しました", emo
                )
        else:
            await interaction.response.send_message(
                f"Preset '{style}' not found.", ephemeral=True
            )

    @app_commands.command(name="presets", description="プリセット一覧")
    async def list_presets(self, interaction: discord.Interaction):
        presets = self.tts_provider.get_presets()
        disp = "\n".join(presets[:20])
        if len(presets) > 20:
            disp += f"\n...and {len(presets) - 20} more."
        await interaction.response.send_message(f"**Presets:**\n{disp}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        # Auto Join
        if before.channel != after.channel and after.channel is not None:
            vc = member.guild.voice_client
            if vc is None:
                try:
                    vc = await after.channel.connect()
                except Exception:
                    return

            if vc.channel == after.channel:
                text, emo = self._get_response("join_greet_normal")
                self.enqueue_speech(vc, text or "こんにちは", emo)

        vc = member.guild.voice_client
        if vc and after.channel == vc.channel:
            # 状態変化イベント
            events = [
                (before.self_mute, after.self_mute, "mute_start", "mute_end"),
                (before.self_deaf, after.self_deaf, "deaf_start", "deaf_end"),
                (before.self_stream, after.self_stream, "stream_start", "stream_end"),
                (before.self_video, after.self_video, "video_start", "video_end"),
            ]
            for b_state, a_state, k_start, k_end in events:
                if b_state != a_state:
                    key = k_start if a_state else k_end
                    text, emo = self._get_response(key)
                    if text:
                        self.enqueue_speech(vc, text, emo)

        # Auto Disconnect
        if vc and before.channel == vc.channel:
            human_count = sum(1 for m in vc.channel.members if not m.bot)
            if human_count == 0:
                await vc.disconnect()


async def setup(bot):
    await bot.add_cog(AudioSystem(bot))
