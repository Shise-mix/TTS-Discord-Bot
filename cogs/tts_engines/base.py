from abc import ABC, abstractmethod


class TTSProvider(ABC):
    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def generate_audio(self, text: str, emotion: str, output_path: str):
        pass

    @abstractmethod
    def get_presets(self) -> list[str]:
        pass

    @abstractmethod
    def set_preset(self, preset_name: str) -> bool:
        pass

    @abstractmethod
    def terminate(self):
        pass
