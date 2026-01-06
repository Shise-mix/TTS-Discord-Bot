import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import uuid
import logging
import traceback
import io
import random
import settings
from .consts import load_json, extract_emotion
from .tts_engines import get_tts_provider

# Rust拡張モジュールのインポート
try:
    import rust_core
except ImportError:
    # 万が一ビルドされていない場合の安全策（本来はここで止めるべきですが）
    print(
        "[CRITICAL] 'rust_core' module not found. Make sure you have built the Rust extension."
    )
    rust_core = None

# ロガーの設定
logger = logging.getLogger(__name__)


class RustAudioSource(discord.AudioSource):
    """
    Rustによってプリロード・リサンプリングされたPCMデータを
    メモリ上から再生するためのDiscord用AudioSourceクラス。
    """

    def __init__(self, pcm_data: bytes):
        self.stream = io.BytesIO(pcm_data)

    def read(self):
        # Discordは20ms分の音声データを要求する (3840 bytes = 48kHz * 2ch * 16bit * 20ms)
        return self.stream.read(3840)

    def is_opus(self):
        # 生のPCMデータなのでFalse
        return False


class AudioSystem(commands.Cog):
    """
    音声再生システム.
    Rust拡張モジュール(rust_core)を使用して、音声加工およびPCMデータへの変換を行う。
    GC停止の影響を受けない安定した配信を実現する。
    """

    def __init__(self, bot):
        self.bot = bot
        self.speech_queue = asyncio.Queue()

        # TTSエンジンの初期化
        engine_name = getattr(settings, "TTS_ENGINE", "aivoice")
        self.tts_provider = get_tts_provider(engine_name)
        self.tts_provider.initialize()

        # 起動時キャラクターの適用
        start_char = getattr(settings, "STARTUP_CHARACTER", None)
        if start_char:
            logger.info(f"Applying startup character: {start_char}")
            if not self.tts_provider.set_preset(start_char):
                logger.warning(f"Failed to set startup character: {start_char}")

        self.voice_data = load_json("responses.json", {})
        self.daily_log = load_json("daily_log.json", {})
        self.word_dict = load_json("dictionary.json", {})

        self.bg_task = self.bot.loop.create_task(self.process_queue())

    def cog_unload(self):
        self.bg_task.cancel()
        if self.tts_provider:
            self.tts_provider.terminate()

    async def process_queue(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                task = await self.speech_queue.get()
                vc_client, text, emotion = task

                if vc_client and vc_client.is_connected():
                    await self.bot.loop.run_in_executor(
                        None, self.speak_internal, vc_client, text, emotion
                    )

                self.speech_queue.task_done()
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    def speak_internal(self, vc_client, text, emotion="JOY"):
        """
        音声合成 -> Rustによる加工(Trim/Gain/Reverb) -> メモリへのロード
        """
        # Rustモジュールがない場合は何もしない
        if not rust_core:
            logger.error("Rust core module is missing. Cannot process audio.")
            return

        EMOTION_MAP = {
            "HAPPY": "JOY",
            "GLAD": "JOY",
            "EXCITED": "JOY",
            "SMILE": "JOY",
            "SAD": "SAD",
            "CRY": "SAD",
            "SORRY": "SAD",
            "ANXIOUS": "SAD",
            "ANGRY": "ANGRY",
            "MAD": "ANGRY",
            "DETERMINED": "ANGRY",
            "SURPRISE": "SURPRISE",
            "SHOCK": "SURPRISE",
            "CONFUSED": "SURPRISE",
            "NORMAL": "NORMAL",
        }
        emotion = EMOTION_MAP.get(emotion, emotion)

        # 辞書置換
        for word, reading in self.word_dict.items():
            text = text.replace(word, reading)

        tmp_filename = f"temp_{uuid.uuid4()}.wav"
        full_path = os.path.abspath(tmp_filename)

        try:
            # 1. 音声生成 (TTSエンジン)
            self.tts_provider.generate_audio(text, emotion, full_path)

            if os.path.exists(full_path):
                # 2. Rustによる加工チェーン
                try:
                    current_path = full_path

                    # Trim (無音カット)
                    trim_out = current_path.replace(".wav", "_trim.wav")
                    rust_core.trim_silence(current_path, trim_out, 100)
                    if os.path.exists(trim_out):
                        self.cleanup_file(current_path)
                        current_path = trim_out

                    # Gain (音量ブースト)
                    gain_out = current_path.replace(".wav", "_gain.wav")
                    rust_core.apply_gain(current_path, gain_out, 3.0)
                    if os.path.exists(gain_out):
                        self.cleanup_file(current_path)
                        current_path = gain_out

                    # Reverb (残響付加) - 必要に応じてパラメータ調整 (delay_ms, decay, mix)
                    reverb_out = current_path.replace(".wav", "_reverb.wav")
                    rust_core.apply_reverb(current_path, reverb_out, 50, 0.3, 0.15)
                    if os.path.exists(reverb_out):
                        self.cleanup_file(current_path)
                        current_path = reverb_out

                    # 3. RustによるPCMロード & リサンプリング (Discord形式へ変換)
                    # ノイズ対策（パディング・アライメント調整）もここで行われる
                    # 返り値は Python の bytes オブジェクト
                    pcm_bytes = rust_core.load_pcm_data(current_path)

                    # メモリに載せたのでファイルは即削除
                    self.cleanup_file(current_path)

                    # メモリ再生用のSourceを作成
                    audio_source = RustAudioSource(pcm_bytes)

                    # 再生予約 (メインループで実行)
                    future = asyncio.run_coroutine_threadsafe(
                        self.play_audio_source(vc_client, audio_source), self.bot.loop
                    )
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Play schedule failed: {e}")

                except Exception as e:
                    logger.error(f"Audio processing failed: {e}")
                    logger.error(traceback.format_exc())
                    self.cleanup_file(full_path)
            else:
                logger.warning(f"Audio generation failed: {full_path}")

        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
            logger.error(traceback.format_exc())
        finally:
            self.cleanup_file(full_path)

    async def play_audio_source(self, vc_client, audio_source):
        if not vc_client.is_connected():
            return
        try:

            def after_playing(error):
                if error:
                    logger.error(f"Playback error: {error}")
                # RustAudioSourceはメモリなのでファイル削除処理は不要

            vc_client.play(audio_source, after=after_playing)

            while vc_client.is_playing():
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Audio playback exception: {e}")

    def cleanup_file(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
            txt_path = path.replace(".wav", ".txt")
            if os.path.exists(txt_path):
                os.remove(txt_path)
        except OSError:
            pass

    def enqueue_speech(self, vc_client, text, emotion="JOY"):
        logger.info(f"Audio Enqueued: {text} ({emotion})")
        self.speech_queue.put_nowait((vc_client, text, emotion))

    def _get_response(self, key, **kwargs):
        raw_val = settings.RESPONSES.get(key, "")
        if not raw_val:
            return None, "NORMAL"
        template = random.choice(raw_val) if isinstance(raw_val, list) else raw_val
        try:
            text = template.format(**kwargs)
        except Exception:
            text = template
        return extract_emotion(text)

    # --- Commands ---

    @app_commands.command(name="join", description="ボイスチャンネルに接続します")
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice:
            vc = await interaction.user.voice.channel.connect()
            await interaction.response.send_message("Connected.")
            text, emo = self._get_response("join_greet_first")
            if not text:
                text, emo = "接続しました。", "JOY"
            self.enqueue_speech(vc, text, emo)
        else:
            await interaction.response.send_message(
                "User is not in a voice channel.", ephemeral=True
            )

    @app_commands.command(
        name="speak", description="【デバッグ用】指定テキストを読み上げます"
    )
    async def speak_test(self, interaction: discord.Interaction, text: str):
        vc = interaction.guild.voice_client
        if vc and vc.is_connected():
            await interaction.response.send_message(f"Test speak: {text}")
            self.enqueue_speech(vc, text, "JOY")
        else:
            await interaction.response.send_message(
                "Bot is not connected to VC.", ephemeral=True
            )

    @app_commands.command(
        name="stop", description="読み上げを停止し、キューをクリアします"
    )
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        await interaction.response.send_message("Playback stopped and queue cleared.")

    @app_commands.command(name="bye", description="ボイスチャンネルから切断します")
    async def bye(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            await interaction.response.send_message("Disconnecting...")
            text, emo = self._get_response("disconnect_msg")
            if text:
                self.enqueue_speech(vc, text, emo)

            # 再生完了まで待機
            await self.speech_queue.join()

            await vc.disconnect()
        else:
            await interaction.response.send_message("Not connected.", ephemeral=True)

    async def preset_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        presets = self.tts_provider.get_presets()
        if not presets:
            return []
        return [
            app_commands.Choice(name=p, value=p)
            for p in presets
            if current.lower() in p.lower()
        ][:25]

    @app_commands.command(name="char", description="TTSキャラクターを変更します")
    @app_commands.autocomplete(style=preset_autocomplete)
    async def char(self, interaction: discord.Interaction, style: str):
        if self.tts_provider.set_preset(style):
            await interaction.response.send_message(
                f"Character changed to: **{style}**"
            )
            if interaction.guild.voice_client:
                text, emo = self._get_response("char_change_voice")
                if not text:
                    text, emo = "交代しました。", "JOY"
                self.enqueue_speech(interaction.guild.voice_client, text, emo)
        else:
            await interaction.response.send_message(
                f"Preset '{style}' not found.", ephemeral=True
            )

    @app_commands.command(
        name="presets", description="利用可能なキャラクター一覧を表示します"
    )
    async def list_presets(self, interaction: discord.Interaction):
        presets = self.tts_provider.get_presets()
        if not presets:
            await interaction.response.send_message(
                "No presets available.", ephemeral=True
            )
            return
        disp = "\n".join(presets[:20])
        if len(presets) > 20:
            disp += f"\n...and {len(presets) - 20} more."
        await interaction.response.send_message(f"**Available Presets:**\n{disp}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        if before.channel != after.channel and after.channel is not None:
            vc = member.guild.voice_client
            if vc is None:
                try:
                    vc = await after.channel.connect()
                    logger.info(f"Auto-joined channel: {after.channel.name}")
                except Exception:
                    return
            if vc.channel == after.channel:
                text, emo = self._get_response("join_greet_normal")
                if not text:
                    text, emo = f"{member.display_name}さん、こんにちは。", "JOY"
                self.enqueue_speech(vc, text, emo)

        vc = member.guild.voice_client
        if vc and after.channel == vc.channel:
            if before.self_mute != after.self_mute:
                key = "mute_start" if after.self_mute else "mute_end"
                text, emo = self._get_response(key)
                if text:
                    self.enqueue_speech(vc, text, emo)
            if before.self_deaf != after.self_deaf:
                key = "deaf_start" if after.self_deaf else "deaf_end"
                text, emo = self._get_response(key)
                if text:
                    self.enqueue_speech(vc, text, emo)
            if before.self_stream != after.self_stream:
                key = "stream_start" if after.self_stream else "stream_end"
                text, emo = self._get_response(key)
                if text:
                    self.enqueue_speech(vc, text, emo)
            if before.self_video != after.self_video:
                key = "video_start" if after.self_video else "video_end"
                text, emo = self._get_response(key)
                if text:
                    self.enqueue_speech(vc, text, emo)

        if vc and before.channel == vc.channel:
            human_count = sum(1 for m in vc.channel.members if not m.bot)
            if human_count == 0:
                logger.info("No users left. Disconnecting.")
                await vc.disconnect()


async def setup(bot):
    await bot.add_cog(AudioSystem(bot))
