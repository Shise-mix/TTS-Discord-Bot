from pydantic import BaseModel, Field
from typing import List


class CharacterResponses(BaseModel):
    """キャラクターのセリフ設定"""

    # 必須ではないフィールドにはデフォルト値を与える
    alarm_set_text: List[str] = Field(default=["セットしたよ！"])
    alarm_set_voice: List[str] = Field(default=["セットしました。[NORMAL]"])
    alarm_list_empty_text: str = "アラームはないよ"
    alarm_list_empty_voice: str = "アラームはありません。[NORMAL]"
    alarm_list_voice: str = "アラーム一覧だよ。[NORMAL]"
    alarm_delete_text: str = "削除したよ"
    alarm_delete_voice: List[str] = Field(default=["削除しました。[NORMAL]"])
    alarm_notify_text: List[str] = Field(default=["時間だよ！"])
    alarm_notify_voice: List[str] = Field(default=["時間になりました。[NORMAL]"])

    dict_add_text: str = "覚えたよ"
    dict_add_voice: List[str] = Field(default=["覚えました。[JOY]"])
    dict_delete_text: str = "忘れたよ"
    dict_delete_voice: str = "忘れました。[NORMAL]"
    dict_empty_text: str = "辞書は空だよ"
    dict_empty_voice: str = "辞書は空っぽです。[NORMAL]"
    dict_list_voice: str = "辞書一覧だよ。[NORMAL]"

    timer_set_text: str = "{minutes}分後に教えるね"
    timer_set_voice: List[str] = Field(default=["タイマーセット。[NORMAL]"])
    timer_list_empty_text: str = "タイマーはないよ"
    timer_list_empty_voice: str = "動いているタイマーはありません。[NORMAL]"
    timer_list_voice: str = "タイマー一覧だよ。[NORMAL]"
    timer_delete_text: str = "タイマー削除"
    timer_delete_voice: str = "タイマーを消しました。[NORMAL]"
    timer_notify_text: List[str] = Field(default=["時間だよ！"])
    timer_notify_voice: List[str] = Field(default=["時間になりました。[NORMAL]"])

    dice_result_voice: List[str] = Field(default=["結果は{total}だよ。[NORMAL]"])
    dice_critical_text: str = "\nクリティカル！"
    dice_critical_voice: List[str] = Field(default=["クリティカル！[JOY]"])
    dice_fumble_text: str = "\nファンブル..."
    dice_fumble_voice: List[str] = Field(default=["ファンブル...[SAD]"])

    join_greet_first: List[str] = Field(default=["こんにちは！[JOY]"])
    join_greet_normal: List[str] = Field(default=["はい！[JOY]"])

    mute_start: List[str] = Field(default=["ミュートします。[NORMAL]"])
    mute_end: List[str] = Field(default=["ミュート解除。[JOY]"])
    deaf_start: str = "スピーカーオフ。[NORMAL]"
    deaf_end: str = "スピーカーオン。[JOY]"
    stream_start: str = "配信開始！[JOY]"
    stream_end: str = "配信終了。[NORMAL]"
    video_start: str = "カメラオン。[JOY]"
    video_end: str = "カメラオフ。[NORMAL]"

    move_voice: List[str] = Field(default=["移動しました。[NORMAL]"])
    char_change_voice: List[str] = Field(default=["交代しました。[JOY]"])
    disconnect_msg: List[str] = Field(default=["またね！[JOY]"])
    chat_error_reply: List[str] = Field(default=["エラーです。[SAD]"])

    # 辞書型としてアクセス可能にする設定
    class Config:
        extra = "ignore"  # 定義されていないキーは無視する


class CharacterConfig(BaseModel):
    """キャラクター設定全体"""

    responses: CharacterResponses
