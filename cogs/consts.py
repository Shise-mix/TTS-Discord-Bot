import json
import os
import re
import logging
from typing import Type, TypeVar
from pydantic import BaseModel

logger = logging.getLogger(__name__)

TAG_PATTERN = r"[\[【(（]\s*[A-Z]+\s*[\]】)）]"
T = TypeVar("T", bound=BaseModel)


def load_json(filename, default):
    """
    JSONファイルを読み込み、辞書(dict)として返します。
    読み込みに失敗した場合やファイルが存在しない場合はデフォルト値を返します。
    ※後方互換性のために残されています。
    """
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default
    return default


def load_pydantic_model(filename: str, model_class: Type[T]) -> T:
    """
    JSONファイルを読み込み、指定されたPydanticモデルに変換して返します。
    ファイルが存在しない場合や解析エラー時は、デフォルト値（初期状態のモデル）を返します。
    """
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            return model_class.parse_obj(data)
        except Exception as e:
            logger.error(f"Failed to load model from {filename}: {e}")
            return model_class()  # デフォルト値で返す
    return model_class()


def save_json(filename, data):
    """データをJSONファイルとして保存する"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")


def extract_emotion(text):
    """
    テキスト末尾の感情タグを抽出して削除する
    """
    if not isinstance(text, str):
        return str(text), "JOY"

    # タグ全体を検索
    match = re.search(TAG_PATTERN, text)
    emotion = "JOY"  # デフォルト
    clean_text = text

    if match:
        # タグが見つかった場合、その中からアルファベット部分だけを再抽出
        tag_str = match.group()  # 例: "[SAD]"
        emo_match = re.search(r"[A-Z]+", tag_str)
        if emo_match:
            emotion = emo_match.group()  # "SAD"

        # タグ部分を空文字に置換して削除
        clean_text = re.sub(TAG_PATTERN, "", text).strip()

    return clean_text, emotion


def parse_emotions(text):
    """
    文章を感情タグでのみ分割してリスト化する．
    句読点による強制分割は行わない．
    """
    # 1. タグで分割する
    # TAG_PATTERN自体にはキャプチャを含まないため、()で囲んでタグ自体を区切り文字として残す
    parts = re.split(f"({TAG_PATTERN})", text)

    segments = []
    buffer_text = ""

    for part in parts:
        # 分割結果がタグの形をしているか判定
        if re.match(TAG_PATTERN, part):
            # タグの中から感情名を取り出す
            emotion_match = re.search(r"[A-Z]+", part)
            if emotion_match:
                emotion = emotion_match.group()
                # バッファにあるテキストと、このタグの感情をセットにする
                if buffer_text.strip():
                    segments.append((buffer_text.strip(), emotion))
                buffer_text = ""
        else:
            # タグでない部分はテキストとしてバッファに追加
            buffer_text += part

    # 末尾の処理（タグがない、またはタグ後のテキスト）
    if buffer_text.strip():
        # 直前の感情があればそれを引き継ぐ、なければNORMAL
        last_emotion = segments[-1][1] if segments else "NORMAL"
        segments.append((buffer_text.strip(), last_emotion))

    return segments
