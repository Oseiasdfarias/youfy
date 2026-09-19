from __future__ import annotations

import torch
from torch import nn


class GenreCNN(nn.Module):
    """CNN pequena sobre mel-espectrograma.

    Termina em AdaptiveAvgPool2d(1), então é independente de `n_mels` e
    `n_frames` — mudar a FeatureSpec não obriga a recalcular a cabeça.
    """

    def __init__(self, n_classes: int, channels: tuple[int, ...] = (16, 32, 64)) -> None:
        super().__init__()
        camadas: list[nn.Module] = []
        entrada = 1
        for c in channels:
            camadas += [
                nn.Conv2d(entrada, c, kernel_size=3, padding=1),
                nn.BatchNorm2d(c),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
            ]
            entrada = c
        self.features = nn.Sequential(*camadas)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(entrada, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.features(x)
        h = self.pool(h).flatten(1)
        return self.head(h)
