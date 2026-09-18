from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from .errors import UnreadableAudio


@dataclass(frozen=True, slots=True)
class AudioProbe:
    duration_s: float
    sample_rate: int
    channels: int

def probe(path: str | Path) -> AudioProbe:
    """Lê apenas o cabeçalho. Barato o suficiente para rodar em todo o dump."""
    try:
        info = sf.info(str(path))
    except Exception as exc:  # soundfile levanta tipos variados por backend
        raise UnreadableAudio(f"nao foi possivel ler o cabecalho de {path}: {exc}") from exc
    return AudioProbe(
        duration_s=float(info.duration),
        sample_rate=int(info.samplerate),
        channels=int(info.channels),
    )

def decode(path: str | Path, target_sample_rate: int) -> np.ndarray:
    """Decodifica para mono float32 no sample rate alvo."""
    try:
        samples, _ = librosa.load(str(path), sr=target_sample_rate, mono=True)
    except Exception as exc:
        raise UnreadableAudio(f"nao foi possivel decodificar {path}: {exc}") from exc
    if samples.size == 0:
        raise UnreadableAudio(f"{path} decodificou para zero amostras")
    return np.asarray(samples, dtype=np.float32)
