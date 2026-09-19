from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from .artifact import GenreClassifier
from .dataset import LabeledTrack


@dataclass(frozen=True, slots=True)
class Metrics:
    macro_f1: float
    accuracy: float
    per_class_f1: dict[str, float]
    confusion: list[list[int]]

    def as_flat_dict(self) -> dict[str, float]:
        plano = {"macro_f1": self.macro_f1, "accuracy": self.accuracy}
        plano.update({f"f1__{c}": v for c, v in self.per_class_f1.items()})
        return plano


def evaluate(
    classifier: GenreClassifier, *, samples: list[LabeledTrack], features_dir: Path
) -> Metrics:
    features_dir = Path(features_dir)
    indice = {c: i for i, c in enumerate(classifier.classes)}

    verdadeiros: list[int] = []
    preditos: list[int] = []
    for amostra in samples:
        arr = np.load(features_dir / f"{amostra.track_id}.npy").astype(np.float32)
        verdadeiros.append(indice[amostra.label])
        preditos.append(int(np.argmax(classifier.predict(arr))))

    rotulos = list(range(len(classifier.classes)))
    f1_por_classe = f1_score(
        verdadeiros, preditos, labels=rotulos, average=None, zero_division=0
    )
    return Metrics(
        macro_f1=float(
            f1_score(verdadeiros, preditos, labels=rotulos, average="macro", zero_division=0)
        ),
        accuracy=float(accuracy_score(verdadeiros, preditos)),
        per_class_f1={c: float(v) for c, v in zip(classifier.classes, f1_por_classe)},
        confusion=confusion_matrix(verdadeiros, preditos, labels=rotulos).tolist(),
    )
