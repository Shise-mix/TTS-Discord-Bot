from .aivoice import AIVoiceProvider
from .voicevox import VoicevoxProvider
import logging

logger = logging.getLogger(__name__)


def get_tts_provider(engine_name: str):
    engine_name = engine_name.lower()

    if engine_name == "voicevox":
        logger.info("TTS Engine selected: VOICEVOX")
        return VoicevoxProvider()

    # デフォルトフォールバック
    logger.info("TTS Engine selected: A.I.VOICE")
    return AIVoiceProvider()
