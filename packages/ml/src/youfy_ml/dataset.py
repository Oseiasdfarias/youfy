from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class MissingFeature(Exception):
    """Array de feature ausente para uma faixa que o split declarou existir."""


@dataclass(frozen=True, slots=True)
class LabeledTrack:
    track_id: str
    label: str


class MelspecDataset(Dataset):
    """Lê `<features_dir>/<track_id>.npy` e devolve `(tensor, indice da classe)`.

    Não consulta banco: recebe os rótulos prontos. É o que mantém `ml`
    treinável a partir de um diretório de arrays.
    """

    def __init__(
        self, samples: list[LabeledTrack], *, features_dir: Path, classes: list[str]
    ) -> None:
        desconhecidos = {a.label for a in samples} - set(classes)
        if desconhecidos:
            raise ValueError(f"rotulos fora das classes canonicas: {sorted(desconhecidos)}")
        self.samples = list(samples)
        self.features_dir = Path(features_dir)
        self.classes = list(classes)
        self._indice = {c: i for i, c in enumerate(self.classes)}

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, int]:
        amostra = self.samples[i]
        caminho = self.features_dir / f"{amostra.track_id}.npy"
        if not caminho.exists():
            raise MissingFeature(f"feature ausente para {amostra.track_id}: {caminho}")
        arr = np.load(caminho).astype(np.float32)
        return torch.from_numpy(arr)[None, :, :], self._indice[amostra.label]
