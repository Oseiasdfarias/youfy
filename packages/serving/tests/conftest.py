"""Fixture compartilhada pelos dois modulos de teste do `serving`.

Vive no conftest, nao num modulo de teste: importar fixture de um test_*.py
para outro funciona por acidente e obriga a `noqa` espalhado.
"""

import pytest
from youfy_audio.spec import FeatureSpec
from youfy_ml.evaluate import Metrics
from youfy_ml.testing import escrever_features
from youfy_ml.tracking import log_run, promote
from youfy_ml.train import TrainConfig, train

SPEC = FeatureSpec(n_mels=16, n_frames=20)
MODELO = "youfy-genre-clf"


@pytest.fixture
def registry_com_campeao(tmp_path):
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    amostras, classes = escrever_features(
        tmp_path, n_classes=8, por_classe=4, n_mels=16, n_frames=20
    )
    config = TrainConfig(seed=0, epochs=2, batch_size=8)
    resultado = train(
        config,
        train_samples=amostras,
        val_samples=amostras,
        features_dir=tmp_path,
        classes=classes,
        feature_spec=SPEC,
    )
    info = log_run(
        tracking_uri=uri,
        experiment="serving",
        config=config,
        result=resultado,
        metrics=Metrics(0.7, 0.7, {"g0": 0.7}, [[1]]),
        register_as=MODELO,
    )
    promote(tracking_uri=uri, model_name=MODELO, version=info.model_version)
    return uri, info.model_version
