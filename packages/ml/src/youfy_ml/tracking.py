from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from .evaluate import Metrics
from .train import TrainConfig, TrainResult

ALIAS_PRODUCAO = "production"
CAMINHO_ARTEFATO = "model"
ARQUIVO_METRICAS = "metrics.json"


@dataclass(frozen=True, slots=True)
class RunInfo:
    run_id: str
    model_version: str | None


def log_run(
    *,
    tracking_uri: str,
    experiment: str,
    config: TrainConfig,
    result: TrainResult,
    metrics: Metrics,
    register_as: str,
) -> RunInfo:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    mlflow.set_experiment(experiment)

    client = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    try:
        client.create_registered_model(register_as)
    except MlflowException:
        pass

    with mlflow.start_run() as run:
        mlflow.log_params({k: str(v) for k, v in asdict(config).items()})
        mlflow.log_param("classes", ",".join(result.classifier.classes))
        mlflow.log_param("feature_fingerprint", result.classifier.feature_spec.fingerprint())

        for epoca in result.history:
            mlflow.log_metric("train_loss", epoca.train_loss, step=epoca.epoch)
            mlflow.log_metric("train_acc", epoca.train_acc, step=epoca.epoch)
            mlflow.log_metric("val_loss", epoca.val_loss, step=epoca.epoch)
            mlflow.log_metric("val_acc", epoca.val_acc, step=epoca.epoch)

        mlflow.log_metrics(metrics.as_flat_dict())

        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / CAMINHO_ARTEFATO
            result.classifier.save(pasta)
            # As metricas viajam junto com o artefato: e assim que o gate le o
            # campeao sem precisar rastrear de qual run ele veio.
            (pasta / ARQUIVO_METRICAS).write_text(json.dumps(asdict(metrics), indent=2))
            mlflow.log_artifacts(str(pasta), artifact_path=CAMINHO_ARTEFATO)

        versao = client.create_model_version(
            name=register_as,
            source=f"runs:/{run.info.run_id}/{CAMINHO_ARTEFATO}",
            run_id=run.info.run_id,
        )
        return RunInfo(run_id=run.info.run_id, model_version=versao.version)


def promote(*, tracking_uri: str, model_name: str, version: str) -> None:
    mlflow.set_registry_uri(tracking_uri)
    MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri).set_registered_model_alias(
        name=model_name, alias=ALIAS_PRODUCAO, version=version
    )


def load_champion_metrics(*, tracking_uri: str, model_name: str) -> Metrics | None:
    cliente = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    try:
        versao = cliente.get_model_version_by_alias(model_name, ALIAS_PRODUCAO)
    except MlflowException:
        return None

    mlflow.set_tracking_uri(tracking_uri)
    local = mlflow.artifacts.download_artifacts(
        run_id=versao.run_id, artifact_path=f"{CAMINHO_ARTEFATO}/{ARQUIVO_METRICAS}"
    )
    return Metrics(**json.loads(Path(local).read_text()))
