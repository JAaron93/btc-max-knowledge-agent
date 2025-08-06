from dataclasses import dataclass

@dataclass
class TTSState:
    enabled: bool = True
    volume: float = 1.0

def create_ui():
    return {'ui': 'placeholder'}

def get_query_function():
    def _query(text: str) -> str:
        return text
    return _query

def create_waveform_animation():
    return {'animation': 'waveform'}


def get_tts_status_display(state: TTSState) -> str:
    return f"TTS: {'On' if state.enabled else 'Off'} (vol={state.volume})"


def set_tts_enabled(state: TTSState, enabled: bool) -> TTSState:
    state.enabled = bool(enabled)
    return state


def set_tts_volume(state: TTSState, volume: float) -> TTSState:
    state.volume = max(0.0, min(1.0, float(volume)))
    return state


def is_tts_enabled(state: TTSState) -> bool:
    return bool(state.enabled)


def get_volume_level(state: TTSState) -> float:
    return float(state.volume)
