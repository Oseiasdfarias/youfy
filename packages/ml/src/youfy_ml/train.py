# packages/ml/src/youfy_ml/train.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from youfy_audio.spec import FeatureSpec

from .artifact import TorchGenreClassifier
from .dataset import LabeledTrack, MelspecDataset
from .model import GenreCNN
from .seeding import seeded_generator, set_seed, worker_init


@dataclass(frozen=True, slots=True)
class TrainConfig:
    seed: int = 42
    epochs: int = 10
    batch_size: int = 32
    lr: float = 1e-3
    channels: tuple[int, ...] = (16, 32, 64)
    num_workers: int = 0


@dataclass(frozen=True, slots=True)
class EpochMetrics:
    epoch: int
    train_loss: float
    train_acc: float
    val_loss: float
    val_acc: float


@dataclass
class TrainResult:
    classifier: TorchGenreClassifier
    history: list[EpochMetrics] = field(default_factory=list)
    final_train_acc: float = 0.0


def train(
    config: TrainConfig,
    *,
    train_samples: list[LabeledTrack],
    val_samples: list[LabeledTrack],
    features_dir: Path,
    classes: list[str],
    feature_spec: FeatureSpec,
) -> TrainResult:
    if config.num_workers != 0:
        raise ValueError(
            "num_workers deve ser 0: workers paralelos quebram a reprodutibilidade "
            "exigida pelo criterio 11 da spec"
        )

    set_seed(config.seed)
    gerador = seeded_generator(config.seed)

    ds_train = MelspecDataset(train_samples, features_dir=features_dir, classes=classes)
    ds_val = MelspecDataset(val_samples, features_dir=features_dir, classes=classes)
    dl_train = DataLoader(
        ds_train,
        batch_size=config.batch_size,
        shuffle=True,
        generator=gerador,
        num_workers=0,
        worker_init_fn=worker_init,
        drop_last=False,
    )
    dl_val = DataLoader(ds_val, batch_size=config.batch_size, shuffle=False, num_workers=0)

    modelo = GenreCNN(n_classes=len(classes), channels=config.channels)
    otimizador = torch.optim.Adam(modelo.parameters(), lr=config.lr)
    criterio = nn.CrossEntropyLoss()

    historico: list[EpochMetrics] = []
    acc_treino = 0.0
    for epoca in range(config.epochs):
        perda_treino, acc_treino = _passo(modelo, dl_train, criterio, otimizador)
        perda_val, acc_val = _passo(modelo, dl_val, criterio, otimizador=None)
        historico.append(
            EpochMetrics(epoca, perda_treino, acc_treino, perda_val, acc_val)
        )

    classificador = TorchGenreClassifier(
        module=modelo, feature_spec=feature_spec, classes=classes
    )
    return TrainResult(classifier=classificador, history=historico, final_train_acc=acc_treino)


def _passo(modelo, loader, criterio, otimizador) -> tuple[float, float]:
    treinando = otimizador is not None
    modelo.train(treinando)
    soma_perda = acertos = total = 0.0

    with torch.set_grad_enabled(treinando):
        for x, y in loader:
            logits = modelo(x)
            perda = criterio(logits, y)
            if treinando:
                otimizador.zero_grad(set_to_none=True)
                perda.backward()
                otimizador.step()
            soma_perda += perda.item() * len(y)
            acertos += float((logits.argmax(dim=-1) == y).sum())
            total += len(y)

    return soma_perda / total, acertos / total
