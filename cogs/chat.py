from discord import app_commands
from discord.ext import commands
import discord
import os
import logging
from openai import AsyncOpenAI, APIConnectionError
import traceback
import random
from collections import deque
import settings
from .consts import extract_emotion, parse_emotions

# ロガーの設定
logger = logging.getLogger(__name__)


class ChatSystem(commands.Cog):
    """
    LLM (Large Language Model) を用いた対話機能を提供するクラス。
    """

    def __init__(self, bot):
        self.bot = bot
        self.llm_client = AsyncOpenAI(
            base_url="http://localhost:1234/v1",
            api_key=os.getenv("LLM_API_KEY", "lm-studio"),
        )
        # 会話履歴を保持する辞書 (channel_id: deque)
        # 各チャンネルごとに最大10ラリー分を保持
        self.histories = {}

    def _get_history(self, channel_id):
        if channel_id not in self.histories:
            self.histories[channel_id] = deque(maxlen=10)
        return self.histories[channel_id]

    @app_commands.command(name="reset", description="LLMとの会話履歴をリセットします")
    async def reset_history(self, interaction: discord.Interaction):
        """現在のチャンネルの会話履歴を消去する"""
        channel_id = interaction.channel_id
        if channel_id in self.histories:
            self.histories[channel_id].clear()
            msg = "会話履歴をリセットしました。[JOY]"
        else:
            msg = "履歴はありませんでした。[NORMAL]"

        clean_text, emotion = extract_emotion(msg)
        await interaction.response.send_message(clean_text)

        # 音声読み上げ
        if interaction.guild and interaction.guild.voice_client:
            audio_cog = self.bot.get_cog("AudioSystem")
            if audio_cog:
                audio_cog.enqueue_speech(
                    interaction.guild.voice_client, clean_text, emotion
                )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        is_mentioned = self.bot.user in message.mentions
        is_reply = (
            message.reference
            and message.reference.resolved
            and message.reference.resolved.author == self.bot.user
        )

        if is_mentioned or is_reply:
            if not settings.SYSTEM_PROMPT:
                return

            async with message.channel.typing():
                try:
                    user_input = message.content.replace(
                        f"<@{self.bot.user.id}>", ""
                    ).strip()

                    if not user_input:
                        return

                    # 履歴の取得と更新
                    history = self._get_history(message.channel.id)
                    history.append({"role": "user", "content": user_input})

                    # LLMへの送信メッセージ構築
                    messages = [{"role": "system", "content": settings.SYSTEM_PROMPT}]
                    messages.extend(history)

                    completion = await self.llm_client.chat.completions.create(
                        model="local-model",
                        messages=messages,
                        temperature=0.7,
                    )

                    response_text = completion.choices[0].message.content

                    # アシスタントの応答を履歴に追加
                    history.append({"role": "assistant", "content": response_text})

                    clean_text, _ = extract_emotion(response_text)
                    await message.reply(clean_text)

                    audio_cog = self.bot.get_cog("AudioSystem")
                    if (
                        audio_cog
                        and message.guild.voice_client
                        and message.guild.voice_client.is_connected()
                    ):
                        segments = parse_emotions(response_text)
                        for text_part, emotion in segments:
                            audio_cog.enqueue_speech(
                                message.guild.voice_client, text_part, emotion
                            )

                except APIConnectionError:
                    logger.error("Failed to connect to LLM server.")
                    await self._send_error_reply(message)

                except Exception as e:
                    logger.error(f"Chat processing failed: {e}")
                    logger.error(traceback.format_exc())
                    await self._send_error_reply(message)

    async def _send_error_reply(self, message):
        try:
            error_replies = settings.RESPONSES.get(
                "chat_error_reply", ["エラーが発生しました。[SAD]"]
            )
            if isinstance(error_replies, list):
                error_msg = random.choice(error_replies)
            else:
                error_msg = error_replies

            clean_msg, emotion = extract_emotion(error_msg)
            await message.reply(clean_msg)

            if message.guild.voice_client and message.guild.voice_client.is_connected():
                audio_cog = self.bot.get_cog("AudioSystem")
                if audio_cog:
                    audio_cog.enqueue_speech(
                        message.guild.voice_client, clean_msg, emotion
                    )

        except Exception as e:
            logger.error(f"Failed to send error reply: {e}")


async def setup(bot):
    await bot.add_cog(ChatSystem(bot))
