from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """Configuração de featurização. Viaja junto com o artefato de modelo.

    n_frames default = 1292 ≈ 30s a 22050 Hz com hop de 512, que é a duração
    dos clipes do FMA.
    """

    sample_rate: int = 22050
    n_fft: int = 2048
    hop_length: int = 512
    n_mels: int = 128
    n_frames: int = 1292
    fmin: float = 0.0
    fmax: float | None = None
    top_db: float = 80.0

    @property
    def effective_fmax(self) -> float:
        return self.fmax if self.fmax is not None else self.sample_rate / 2

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()[:16]
