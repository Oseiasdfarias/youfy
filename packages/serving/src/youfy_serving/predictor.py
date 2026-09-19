from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .loader import LoadedModel


@dataclass(frozen=True, slots=True)
class GenrePrediction:
    distribution: dict[str, float]
    top_genre: str
    model_version: str


class Predictor:
    def __init__(self, loaded: LoadedModel) -> None:
        self._loaded = loaded

    @property
    def model_version(self) -> str:
        return self._loaded.model_version

    def predict(self, melspec: np.ndarray) -> GenrePrediction:
        clf = self._loaded.classifier
        probs = clf.predict(melspec)
        distribuicao = {c: float(p) for c, p in zip(clf.classes, probs)}
        return GenrePrediction(
            distribution=distribuicao,
            top_genre=clf.classes[int(np.argmax(probs))],
            model_version=self._loaded.model_version,
        )
