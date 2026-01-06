import os
import time
import logging

# .NET Framework連携用のライブラリ読み込み
try:
    from pythonnet import load

    load("netfx")
except Exception as e:
    print(f"[WARNING] Pythonnet load failed: {e}")

import clr
from .base import TTSProvider

logger = logging.getLogger(__name__)


class AIVoiceProvider(TTSProvider):
    """
    A.I.VOICE Editor API を利用したTTSプロバイダー．
    .NET DLLを介してエディタを制御する．
    """

    def __init__(self):
        self.tts_control = None
        self.host_status = None
        self.all_presets = []
        self.display_presets = []
        self.current_base_preset = ""

        self.dll_path = os.getenv(
            "AIVOICE_DLL_PATH",
            r"C:\Program Files\AI\AIVoice\AIVoiceEditor\AI.Talk.Editor.Api.dll",
        )

    def initialize(self):
        if not os.path.exists(self.dll_path):
            logger.error(f"A.I.VOICE DLL not found at: {self.dll_path}")
            return

        try:
            clr.AddReference(self.dll_path)
            from AI.Talk.Editor.Api import TtsControl, HostStatus  # type: ignore

            self.tts_control = TtsControl()
            self.host_status = HostStatus

            if not self._ensure_connection():
                logger.warning("Failed to connect to A.I.VOICE Editor.")

            # ★ここが重要: VoicePresetNames を使用してユーザー作成プリセットを取得
            if self.tts_control:
                raw_presets = list(self.tts_control.VoicePresetNames)
                self.all_presets = [str(p) for p in raw_presets]
            else:
                self.all_presets = []

            # ログ出力（確認用）
            logger.info("=== Loaded A.I.VOICE Presets ===")
            for p in self.all_presets:
                logger.info(f" - {p}")
            logger.info("==================================")

            seen = set()
            ignore_suffixes = ["_JOY", "_SAD", "_ANGRY", "_SURPRISE", "_NORMAL", "_SAN"]

            for name in self.all_presets:
                # 表示用: サフィックスを除去してベース名を抽出
                base_name = name
                for suffix in ignore_suffixes:
                    if base_name.endswith(suffix):
                        base_name = base_name[: -len(suffix)]
                        break

                if base_name not in seen:
                    self.display_presets.append(base_name)
                    seen.add(base_name)

            self.display_presets.sort()
            logger.info(f"A.I.VOICE Init: Loaded {len(self.all_presets)} presets.")

        except Exception as e:
            logger.error(f"A.I.VOICE Init Error: {e}")

    def _ensure_connection(self):
        if not self.tts_control:
            return False

        try:
            if self.tts_control.Status == self.host_status.Idle:
                return True
        except Exception:
            pass

        try:
            available_hosts = self.tts_control.GetAvailableHostNames()

            if not available_hosts:
                editor_path = getattr(
                    os.getenv("AIVOICE_APP_PATH"),
                    "default",
                    r"C:\Program Files\AI\AIVoice\AIVoiceEditor\AIVoiceEditor.exe",
                )
                if os.path.exists(editor_path):
                    import subprocess

                    subprocess.Popen(editor_path)
                    for _ in range(10):
                        time.sleep(1)
                        if self.tts_control.GetAvailableHostNames():
                            break

            if self.tts_control.GetAvailableHostNames():
                try:
                    self.tts_control.Initialize(
                        self.tts_control.GetAvailableHostNames()[0]
                    )
                except Exception:
                    pass
                try:
                    self.tts_control.Connect()
                except Exception:
                    pass

            if self.tts_control.Status == self.host_status.Idle:
                return True

        except Exception as e:
            logger.error(f"Connection Retry Failed: {e}")

        return False

    def generate_audio(self, text: str, emotion: str, output_path: str):
        if not self._ensure_connection():
            return

        try:
            target_preset = self.current_base_preset

            # プリセット検索ロジック (以前の正常動作版)
            if emotion == "NORMAL":
                candidate = f"{self.current_base_preset}_NORMAL"
                if candidate in self.all_presets:
                    target_preset = candidate
                elif self.current_base_preset in self.all_presets:
                    target_preset = self.current_base_preset
            else:
                candidate = f"{self.current_base_preset}_{emotion}"
                if candidate in self.all_presets:
                    target_preset = candidate
                else:
                    # 感情プリセットがない場合はNORMAL系にフォールバック
                    normal_candidate = f"{self.current_base_preset}_NORMAL"
                    if normal_candidate in self.all_presets:
                        target_preset = normal_candidate

            # プリセット適用
            if self.tts_control.CurrentVoicePresetName != target_preset:
                self.tts_control.CurrentVoicePresetName = target_preset
                logger.info(f"Switched Preset to: {target_preset}")

            # パラメータ調整の判定
            # ターゲットとしたプリセットが、指定された感情サフィックスで終わっていない場合のみ調整
            should_fallback_param = False
            if emotion != "NORMAL":
                if not target_preset.endswith(f"_{emotion}"):
                    should_fallback_param = True

            if should_fallback_param:
                self._apply_fallback_parameters(emotion)
            else:
                # 正しいプリセットが当たった場合はパラメータをリセット
                self._apply_fallback_parameters("RESET")

            self.tts_control.Text = text
            self.tts_control.SaveAudioToFile(output_path)

        except Exception as e:
            logger.error(f"A.I.VOICE Speak Error: {e}")

    def _apply_fallback_parameters(self, emotion):
        try:
            p, s, r, v = 1.0, 1.0, 1.0, 1.0

            if emotion == "JOY":
                p, s, r = 1.15, 1.05, 1.20
            elif emotion == "SAD":
                p, s, r = 0.92, 0.85, 0.80
            elif emotion == "ANGRY":
                p, s, r, v = 1.05, 1.15, 1.30, 1.10
            elif emotion == "SURPRISE":
                p, s, r = 1.25, 1.10, 1.30
            elif emotion == "RESET":
                pass

            self.tts_control.MasterPitch = p
            self.tts_control.MasterSpeed = s
            self.tts_control.MasterPitchRange = r
            self.tts_control.MasterVolume = v
        except Exception as e:
            logger.error(f"Fallback Param Error: {e}")

    def get_presets(self) -> list[str]:
        self._ensure_connection()
        return self.display_presets

    def set_preset(self, preset_name: str) -> bool:
        if preset_name in self.display_presets:
            self.current_base_preset = preset_name
            return True
        return False

    def terminate(self):
        if self.tts_control:
            try:
                self.tts_control.Disconnect()
                self.tts_control.Terminate()
            except Exception:
                pass
