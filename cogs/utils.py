from .consts import load_json, save_json, extract_emotion
import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import logging
from datetime import datetime, timedelta
import settings

# ロガーの設定
logger = logging.getLogger(__name__)


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.alarm_list = load_json("alarms.json", [])
        self.timer_list = []

        self.config = load_json("config.json", {})
        self.default_alarm_channel_id = int(self.config.get("alarmChannelId", 0))

        self.last_checked_minute = ""

        self.check_alarm_task.start()
        self.check_timer_task.start()

    def cog_unload(self):
        self.check_alarm_task.cancel()
        self.check_timer_task.cancel()

    def save_alarms(self):
        save_json("alarms.json", self.alarm_list)

    def speak(self, guild, text):
        audio_cog = self.bot.get_cog("AudioSystem")
        if audio_cog and guild and guild.voice_client:
            # 共通関数を使用
            clean_text, emotion = extract_emotion(text)
            audio_cog.enqueue_speech(guild.voice_client, clean_text, emotion)

    def get_random_text(self, key, **kwargs):
        raw_val = settings.RESPONSES.get(key, "メッセージが見つかりません")

        if isinstance(raw_val, list):
            template = random.choice(raw_val)
        else:
            template = raw_val

        try:
            return template.format(**kwargs)
        except Exception as e:
            logger.warning(f"Format Error in {key}: {e}")
            return template

    # --- アラーム機能 ---
    alarm_group = app_commands.Group(name="alarm", description="アラームの管理")

    @alarm_group.command(name="add", description="アラームを追加します")
    async def alarm_add(
        self,
        interaction: discord.Interaction,
        time: str,
        message: str,
        repeat: bool = False,
    ):
        clean_time = time.replace(" ", "").replace("：", ":")
        try:
            dt = datetime.strptime(clean_time, "%H:%M")
            formatted_time = dt.strftime("%H:%M")
        except ValueError:
            await interaction.response.send_message(
                "時間は `12:00` のように入力してください", ephemeral=True
            )
            return

        new_alarm = {
            "time": formatted_time,
            "message": message,
            "user_id": interaction.user.id,
            "channel_id": interaction.channel_id,
            "repeat": repeat,
        }
        self.alarm_list.append(new_alarm)
        self.save_alarms()

        icon = "🔄" if repeat else "1️⃣"

        raw_text = self.get_random_text(
            "alarm_set_text", time=formatted_time, icon=icon, message=message
        )
        clean_text, _ = extract_emotion(raw_text)
        await interaction.response.send_message(clean_text)

        res_voice = self.get_random_text("alarm_set_voice", time=formatted_time)
        self.speak(interaction.guild, res_voice)

    @alarm_group.command(name="list", description="アラーム一覧")
    async def alarm_list(self, interaction: discord.Interaction):
        if not self.alarm_list:
            raw_text = self.get_random_text("alarm_list_empty_text")
            clean_text, _ = extract_emotion(raw_text)
            await interaction.response.send_message(clean_text)

            res_voice = self.get_random_text("alarm_list_empty_voice")
            self.speak(interaction.guild, res_voice)
            return

        text = "⏰ **アラーム一覧**\n"
        for i, alarm in enumerate(self.alarm_list):
            icon = "🔄" if alarm["repeat"] else "1️⃣"
            ch_name = ""
            if "channel_id" in alarm:
                ch = interaction.guild.get_channel(alarm["channel_id"])
                if ch:
                    ch_name = f" (in {ch.name})"

            text += (
                f"`{i + 1}`. **{alarm['time']}** {icon} : {alarm['message']}{ch_name}\n"
            )

        res_voice = self.get_random_text("alarm_list_voice")
        await interaction.response.send_message(text)
        self.speak(interaction.guild, res_voice)

    @alarm_group.command(name="delete", description="アラーム削除")
    async def alarm_delete(self, interaction: discord.Interaction, index: int):
        if 1 <= index <= len(self.alarm_list):
            removed = self.alarm_list.pop(index - 1)
            self.save_alarms()

            raw_text = self.get_random_text(
                "alarm_delete_text", time=removed["time"], message=removed["message"]
            )
            clean_text, _ = extract_emotion(raw_text)

            res_voice = self.get_random_text("alarm_delete_voice")

            await interaction.response.send_message(clean_text)
            self.speak(interaction.guild, res_voice)
        else:
            await interaction.response.send_message(
                "その番号のアラームはありません", ephemeral=True
            )

    # --- 辞書機能 ---
    dict_group = app_commands.Group(name="dict", description="読み方辞書の管理")

    @dict_group.command(name="add", description="単語登録")
    async def dict_add(self, interaction: discord.Interaction, word: str, reading: str):
        audio_cog = self.bot.get_cog("AudioSystem")
        if not audio_cog:
            await interaction.response.send_message(
                "音声システムが起動していません", ephemeral=True
            )
            return

        audio_cog.word_dict[word] = reading
        save_json("dictionary.json", audio_cog.word_dict)

        raw_text = self.get_random_text("dict_add_text", word=word, reading=reading)
        clean_text, _ = extract_emotion(raw_text)

        res_voice = self.get_random_text("dict_add_voice", word=word, reading=reading)

        await interaction.response.send_message(clean_text)
        self.speak(interaction.guild, res_voice)

    @dict_group.command(name="delete", description="単語削除")
    async def dict_delete(self, interaction: discord.Interaction, index: int):
        audio_cog = self.bot.get_cog("AudioSystem")
        if not audio_cog:
            return

        keys = list(audio_cog.word_dict.keys())
        if 1 <= index <= len(keys):
            target = keys[index - 1]
            del audio_cog.word_dict[target]
            save_json("dictionary.json", audio_cog.word_dict)

            raw_text = self.get_random_text("dict_delete_text", word=target)
            clean_text, _ = extract_emotion(raw_text)

            res_voice = self.get_random_text("dict_delete_voice", word=target)

            await interaction.response.send_message(clean_text)
            self.speak(interaction.guild, res_voice)
        else:
            await interaction.response.send_message(
                "その番号の単語はありません", ephemeral=True
            )

    @dict_group.command(name="list", description="辞書一覧")
    async def dict_list(self, interaction: discord.Interaction):
        audio_cog = self.bot.get_cog("AudioSystem")
        if not audio_cog or not audio_cog.word_dict:
            raw_text = self.get_random_text("dict_empty_text")
            clean_text, _ = extract_emotion(raw_text)
            await interaction.response.send_message(clean_text)

            res_voice = self.get_random_text("dict_empty_voice")
            self.speak(interaction.guild, res_voice)
            return

        text = "📖 **辞書一覧**\n"
        for i, (k, v) in enumerate(audio_cog.word_dict.items()):
            text += f"`{i + 1}`. {k} → {v}\n"

        res_voice = self.get_random_text("dict_list_voice")
        await interaction.response.send_message(text[:1900])
        self.speak(interaction.guild, res_voice)

    # --- タイマー機能 ---
    timer_group = app_commands.Group(name="timer", description="タイマー管理")

    @timer_group.command(name="set", description="タイマーをセット(分)")
    async def timer_set(self, interaction: discord.Interaction, minutes: int):
        if minutes <= 0:
            await interaction.response.send_message(
                "1分以上で設定してください", ephemeral=True
            )
            return

        end_time = datetime.now() + timedelta(minutes=minutes)
        self.timer_list.append(
            {
                "end_time": end_time,
                "minutes": minutes,
                "user_id": interaction.user.id,
                "channel_id": interaction.channel_id,
            }
        )

        raw_text = self.get_random_text("timer_set_text", minutes=minutes)
        clean_text, _ = extract_emotion(raw_text)

        res_voice = self.get_random_text("timer_set_voice", minutes=minutes)

        await interaction.response.send_message(clean_text)
        self.speak(interaction.guild, res_voice)

    @timer_group.command(name="list", description="稼働中のタイマー")
    async def timer_list(self, interaction: discord.Interaction):
        if not self.timer_list:
            raw_text = self.get_random_text("timer_list_empty_text")
            clean_text, _ = extract_emotion(raw_text)
            await interaction.response.send_message(clean_text)

            res_voice = self.get_random_text("timer_list_empty_voice")
            self.speak(interaction.guild, res_voice)
            return

        now = datetime.now()
        text = "⏳ **タイマー一覧**\n"
        for i, timer in enumerate(self.timer_list):
            remaining = timer["end_time"] - now
            if remaining.total_seconds() < 0:
                rem_m, rem_s = 0, 0
            else:
                rem_m = int(remaining.total_seconds() // 60)
                rem_s = int(remaining.total_seconds() % 60)
            text += (
                f"`{i + 1}`. 残り**{rem_m}分{rem_s}秒** (元: {timer['minutes']}分)\n"
            )

        res_voice = self.get_random_text("timer_list_voice")
        await interaction.response.send_message(text)
        self.speak(interaction.guild, res_voice)

    @timer_group.command(name="delete", description="タイマーをキャンセル")
    async def timer_delete(self, interaction: discord.Interaction, index: int):
        if 1 <= index <= len(self.timer_list):
            removed = self.timer_list.pop(index - 1)

            raw_text = self.get_random_text(
                "timer_delete_text", minutes=removed["minutes"]
            )
            clean_text, _ = extract_emotion(raw_text)

            res_voice = self.get_random_text("timer_delete_voice")

            await interaction.response.send_message(clean_text)
            self.speak(interaction.guild, res_voice)
        else:
            await interaction.response.send_message(
                "その番号のタイマーはありません", ephemeral=True
            )

    # --- ダイス機能 ---
    @app_commands.command(name="dice", description="ダイスを振ります (例: 2d6+1d4-5)")
    async def dice(self, interaction: discord.Interaction, notation: str = "1d100"):
        # タイムアウト対策：先に応答保留にしておく
        await interaction.response.defer()

        clean_notation = notation.replace(" ", "").replace("-", "+-")
        total = 0
        details = []

        try:
            parts = clean_notation.split("+")
            for part in parts:
                if not part:
                    continue

                if "d" in part:
                    count_str, sides_str = part.split("d")
                    count = int(count_str) if count_str else 1

                    # マイナスダイス対応 (例: -1d4)
                    sign = -1 if count < 0 else 1
                    count = abs(count)
                    sides = int(sides_str)

                    if count > 100:
                        # followup で送信
                        await interaction.followup.send(
                            "ダイスの数が多すぎます（100個まで）", ephemeral=True
                        )
                        return

                    rolls = [random.randint(1, sides) for _ in range(count)]
                    part_sum = sum(rolls) * sign
                    total += part_sum

                    details.append(f"{part}({', '.join(map(str, rolls))})")

                else:
                    mod = int(part)
                    total += mod
                    details.append(str(mod))

            detail_str = " + ".join(details).replace("+-", "-")

            msg = f"🎲 **{notation}**\n結果: **{total}**\n内訳: `{detail_str}`"
            voice_text = self.get_random_text("dice_result_voice", total=total)

            # クリティカル・ファンブル判定（入力が "1d100" と完全一致する場合のみ）
            if notation.strip() == "1d100":
                if total <= 5:
                    msg += self.get_random_text("dice_critical_text")
                    voice_text = self.get_random_text(
                        "dice_critical_voice", total=total
                    )
                elif total >= 96:
                    msg += self.get_random_text("dice_fumble_text")
                    voice_text = self.get_random_text("dice_fumble_voice", total=total)

            clean_msg, _ = extract_emotion(msg)
            # followup で送信
            await interaction.followup.send(clean_msg)

            self.speak(interaction.guild, voice_text)

        except Exception as e:
            await interaction.followup.send(f"計算式のエラーです: {e}", ephemeral=True)

    # --- 定期タスク ---
    @tasks.loop(seconds=10)
    async def check_alarm_task(self):
        now_str = datetime.now().strftime("%H:%M")

        if self.last_checked_minute == now_str:
            return

        self.last_checked_minute = now_str
        remove_list = []

        for alarm in self.alarm_list:
            if alarm["time"] == now_str:
                target_channel_id = (
                    alarm.get("channel_id") or self.default_alarm_channel_id
                )

                channel = self.bot.get_channel(target_channel_id)
                if channel:
                    notify_text_raw = self.get_random_text(
                        "alarm_notify_text",
                        user_id=alarm["user_id"],
                        message=alarm["message"],
                    )
                    notify_text_clean, _ = extract_emotion(notify_text_raw)

                    notify_voice = self.get_random_text(
                        "alarm_notify_voice", message=alarm["message"]
                    )

                    await channel.send(notify_text_clean)
                    self.speak(channel.guild, notify_voice)

                if not alarm["repeat"]:
                    remove_list.append(alarm)

        if remove_list:
            for r in remove_list:
                if r in self.alarm_list:
                    self.alarm_list.remove(r)
            self.save_alarms()

    @tasks.loop(seconds=1)
    async def check_timer_task(self):
        now = datetime.now()
        remove_list = []

        for timer in self.timer_list:
            if now >= timer["end_time"]:
                channel = self.bot.get_channel(timer["channel_id"])
                if channel:
                    notify_text_raw = self.get_random_text(
                        "timer_notify_text",
                        minutes=timer["minutes"],
                        user_id=timer["user_id"],
                    )
                    notify_text_clean, _ = extract_emotion(notify_text_raw)

                    notify_voice = self.get_random_text(
                        "timer_notify_voice", minutes=timer["minutes"]
                    )

                    await channel.send(notify_text_clean)
                    self.speak(channel.guild, notify_voice)
                remove_list.append(timer)

        for r in remove_list:
            if r in self.timer_list:
                self.timer_list.remove(r)


async def setup(bot):
    await bot.add_cog(Utilities(bot))
