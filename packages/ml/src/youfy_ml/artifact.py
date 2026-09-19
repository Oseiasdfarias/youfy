# packages/ml/src/youfy_ml/artifact.py
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import torch
from torch import nn
from youfy_audio.spec import FeatureSpec


@runtime_checkable
class GenreClassifier(Protocol):
    """Contrato entre `ml` e `serving`.

    O artefato carrega a própria `FeatureSpec`: o serving não tem permissão de
    assumir que sabe featurizar. É o que converte training/serving skew de
    degradação silenciosa em falha ruidosa na carga.
    """

    feature_spec: FeatureSpec
    classes: list[str]

    def predict(self, melspec: np.ndarray) -> np.ndarray: ...


class TorchGenreClassifier:
    ARQUIVO_PESOS = "pesos.pt"
    ARQUIVO_META = "metadados.json"

    def __init__(self, module: nn.Module, feature_spec: FeatureSpec, classes: list[str]) -> None:
        if not classes:
            raise ValueError("classes nao pode ser vazio: a ordem canonica vive no artefato")
        self.module = module
        self.feature_spec = feature_spec
        self.classes = list(classes)

    def predict(self, melspec: np.ndarray) -> np.ndarray:
        esperado = (self.feature_spec.n_mels, self.feature_spec.n_frames)
        if melspec.shape != esperado:
            raise ValueError(f"shape {melspec.shape} incompativel com a spec do modelo {esperado}")
        self.module.eval()
        with torch.no_grad():
            entrada = torch.from_numpy(np.asarray(melspec, dtype=np.float32))[None, None, :, :]
            logits = self.module(entrada)
            probs = torch.softmax(logits, dim=-1)[0]
        return probs.numpy().astype(np.float32)

    def save(self, destino: Path) -> None:
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        torch.save(self.module, destino / self.ARQUIVO_PESOS)
        (destino / self.ARQUIVO_META).write_text(
            json.dumps(
                {"feature_spec": asdict(self.feature_spec), "classes": self.classes}, indent=2
            )
        )

    @classmethod
    def load(cls, origem: Path) -> TorchGenreClassifier:
        origem = Path(origem)
        meta = json.loads((origem / cls.ARQUIVO_META).read_text())
        modulo = torch.load(origem / cls.ARQUIVO_PESOS, weights_only=False)
        return cls(
            module=modulo,
            feature_spec=FeatureSpec(**meta["feature_spec"]),
            classes=meta["classes"],
        )
