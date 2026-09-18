from __future__ import annotations

import librosa
import numpy as np

from .spec import FeatureSpec


def compute_melspec(
    samples: np.ndarray, sample_rate: int, spec: FeatureSpec
) -> np.ndarray:
    """Mel-espectrograma em dB, com shape fixo `(spec.n_mels, spec.n_frames)`."""
    if sample_rate != spec.sample_rate:
        raise ValueError(
            f"sample rate divergente: recebido {sample_rate}, spec exige {spec.sample_rate}"
        )

    power = librosa.feature.melspectrogram(
        y=np.asarray(samples, dtype=np.float32),
        sr=sample_rate,
        n_fft=spec.n_fft,
        hop_length=spec.hop_length,
        n_mels=spec.n_mels,
        fmin=spec.fmin,
        fmax=spec.effective_fmax,
    )
    # ref=1.0 fixo, nunca np.max: normalizar por clipe destruiria a informação de
    # loudness absoluto e faria a mesma faixa gerar features diferentes conforme o
    # trecho, quebrando a comparabilidade entre treino e serving.
    db = librosa.power_to_db(power, ref=1.0, top_db=spec.top_db)
    return _ajustar_frames(db, spec.n_frames).astype(np.float32)


def _ajustar_frames(db: np.ndarray, n_frames: int) -> np.ndarray:
    atual = db.shape[1]
    if atual == n_frames:
        return db
    if atual > n_frames:
        return db[:, :n_frames]
    preenchimento = np.full((db.shape[0], n_frames - atual), db.min(), dtype=db.dtype)
    return np.concatenate([db, preenchimento], axis=1)
