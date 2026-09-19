"""Acervo sintético com sinal aprendível, para testes de ML rápidos.

Cada classe concentra energia numa faixa distinta do melspec, então um modelo
sadio aprende; com rótulos embaralhados não há o que aprender, e a métrica
volta para o acaso. São 8 classes de propósito: é o número da spec, e o que
faz o limiar de 0,20 do teste de rótulos embaralhados ser o mesmo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from youfy_ml.dataset import LabeledTrack


def escrever_features(
    destino: Path,
    *,
    n_classes: int = 8,
    por_classe: int = 24,
    n_mels: int = 16,
    n_frames: int = 20,
    seed: int = 0,
    embaralhar_rotulos: bool = False,
) -> tuple[list[LabeledTrack], list[str]]:
    destino.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    classes = [f"g{k}" for k in range(n_classes)]
    amostras: list[LabeledTrack] = []
    verdadeiros: list[int] = []

    largura = max(1, n_mels // n_classes)
    for i in range(por_classe):
        for k in range(n_classes):
            arr = rng.normal(0.0, 1.0, size=(n_mels, n_frames)).astype(np.float32)
            inicio = k * largura
            arr[inicio : inicio + largura, :] += 8.0      # a banda que identifica a classe
            track_id = f"fma_track_{k}_{i}"
            np.save(destino / f"{track_id}.npy", arr)
            amostras.append(LabeledTrack(track_id, classes[k]))
            verdadeiros.append(k)

    if embaralhar_rotulos:
        permutados = rng.permutation(verdadeiros)
        amostras = [
            LabeledTrack(a.track_id, classes[int(k)]) for a, k in zip(amostras, permutados)
        ]
    return amostras, classes
