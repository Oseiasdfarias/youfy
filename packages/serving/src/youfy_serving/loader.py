from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from youfy_audio.spec import FeatureSpec
from youfy_ml.artifact import TorchGenreClassifier
from youfy_ml.tracking import ALIAS_PRODUCAO, CAMINHO_ARTEFATO

from .errors import FeatureSpecMismatch, NoProductionModel


@dataclass(frozen=True, slots=True)
class LoadedModel:
    classifier: TorchGenreClassifier
    model_version: str


def load_production(
    *, tracking_uri: str, model_name: str, expected_spec: FeatureSpec
) -> LoadedModel:
    """Resolve o alias de produção e valida a FeatureSpec embutida no artefato.

    A validação é na carga, de propósito: training/serving skew tem que ser
    falha ruidosa na inicialização, nunca degradação silenciosa na predição.
    """
    cliente = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    try:
        versao = cliente.get_model_version_by_alias(model_name, ALIAS_PRODUCAO)
    except MlflowException as exc:
        raise NoProductionModel(
            f"nenhuma versao sob o alias '{ALIAS_PRODUCAO}' para o modelo '{model_name}'"
        ) from exc

    mlflow.set_tracking_uri(tracking_uri)
    local = mlflow.artifacts.download_artifacts(
        run_id=versao.run_id, artifact_path=CAMINHO_ARTEFATO
    )
    classificador = TorchGenreClassifier.load(Path(local))

    if classificador.feature_spec != expected_spec:
        raise FeatureSpecMismatch(
            "a FeatureSpec do artefato diverge da config do featurizer: "
            f"modelo={classificador.feature_spec.fingerprint()} "
            f"({classificador.feature_spec}) contra "
            f"featurizer={expected_spec.fingerprint()} ({expected_spec})"
        )

    return LoadedModel(classifier=classificador, model_version=versao.version)
