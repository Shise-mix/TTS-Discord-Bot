import requests
import json
import os
import logging
from .base import TTSProvider

logger = logging.getLogger(__name__)


class VoicevoxProvider(TTSProvider):
    """
    VOICEVOX EngineのHTTP APIラッパークラス．
    """

    def __init__(self):
        self.base_url = os.getenv("VOICEVOX_URL", "http://127.0.0.1:50021")
        # デフォルトスピーカーID (3: ずんだもん・ノーマル)
        self.current_speaker_id = int(os.getenv("VOICEVOX_SPEAKER_ID", "3"))
        self.speaker_map = {}

    def initialize(self):
        """スピーカー一覧を取得し，IDと名前のマッピングを作成する"""
        try:
            resp = requests.get(f"{self.base_url}/speakers")
            if resp.status_code == 200:
                data = resp.json()
                for chara in data:
                    name = chara["name"]
                    for style in chara["styles"]:
                        # 検索用キー作成: "ずんだもん(ノーマル)"
                        key = f"{name}({style['name']})"
                        self.speaker_map[key] = style["id"]
                logger.info(
                    f"VOICEVOX Initialized. Default ID: {self.current_speaker_id}"
                )
            else:
                logger.error(f"VOICEVOX Connection Failed: Status {resp.status_code}")
        except Exception as e:
            logger.error(f"VOICEVOX Connection Error: {e}")

    def generate_audio(self, text: str, emotion: str, output_path: str):
        """AudioQueryの作成と音声合成の2ステップを実行する"""
        try:
            # 1. Audio Queryの作成（イントネーション等のデータ生成）
            params = {"text": text, "speaker": self.current_speaker_id}
            query_resp = requests.post(f"{self.base_url}/audio_query", params=params)

            if query_resp.status_code != 200:
                logger.error(f"VOICEVOX Query Error: {query_resp.text}")
                return

            query_data = query_resp.json()

            # --- パラメータ調整 ---
            # 感情タグに応じてピッチや抑揚を微調整する
            pitch = 0.0
            speed = 1.0
            intonation = 1.0
            volume = 1.0

            if emotion == "JOY":
                pitch = 0.02
                intonation = 1.10
                speed = 1.02
            elif emotion == "SAD":
                pitch = -0.02
                intonation = 0.95
                speed = 0.98
            elif emotion == "ANGRY":
                speed = 1.05
                intonation = 1.10
                pitch = -0.01
                volume = 1.05
            elif emotion == "SURPRISE":
                pitch = 0.03
                speed = 1.05
                intonation = 1.10

            # パラメータ適用
            query_data["pitchScale"] = pitch
            query_data["speedScale"] = speed
            query_data["intonationScale"] = intonation
            query_data["volumeScale"] = volume

            # 2. 音声合成 (Synthesis)
            headers = {"Content-Type": "application/json"}
            synth_resp = requests.post(
                f"{self.base_url}/synthesis",
                headers=headers,
                params={"speaker": self.current_speaker_id},
                data=json.dumps(query_data),
            )

            if synth_resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(synth_resp.content)
            else:
                logger.error(f"VOICEVOX Synthesis Error: {synth_resp.status_code}")

        except Exception as e:
            logger.error(f"VOICEVOX Generation Exception: {e}")

    def get_presets(self) -> list[str]:
        return list(self.speaker_map.keys())

    def set_preset(self, preset_name: str) -> bool:
        # 完全一致検索
        if preset_name in self.speaker_map:
            self.current_speaker_id = self.speaker_map[preset_name]
            return True
        # 部分一致検索
        for name, pid in self.speaker_map.items():
            if preset_name in name:
                self.current_speaker_id = pid
                return True
        return False

    def terminate(self):
        pass
