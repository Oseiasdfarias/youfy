from __future__ import annotations

import json
from pathlib import Path

import structlog
from sqlalchemy.orm import Session
from youfy_audio.spec import FeatureSpec
from youfy_catalog.queries import known_genres, labeled_tracks_for
from youfy_ml.dataset import LabeledTrack
from youfy_ml.evaluate import evaluate
from youfy_ml.promotion import PromotionDecision, should_promote
from youfy_ml.tracking import RunInfo, load_champion_metrics, log_run, promote
from youfy_ml.train import TrainConfig, train
from youfy_serving.loader import carregar_versao

from .featurize import features_dir
from .split import splits_dir

log = structlog.get_logger()


def load_split(data_dir: Path, spec: FeatureSpec, nome: str) -> list[str]:
    arquivo = splits_dir(data_dir, spec) / f"{nome}.json"
    return json.loads(arquivo.read_text())["track_ids"]


def _amostras(session: Session, data_dir: Path, spec: FeatureSpec, nome: str) -> list[LabeledTrack]:
    ids = load_split(data_dir, spec, nome)
    return [LabeledTrack(r.track_id, r.label) for r in labeled_tracks_for(session, track_ids=ids)]


def run_train(
    session: Session,
    *,
    data_dir: Path,
    spec: FeatureSpec,
    config: TrainConfig,
    tracking_uri: str,
    model_name: str,
    experiment: str = "youfy-genre",
) -> RunInfo:
    classes = known_genres(session)
    resultado = train(
        config,
        train_samples=_amostras(session, data_dir, spec, "train"),
        val_samples=_amostras(session, data_dir, spec, "val"),
        features_dir=features_dir(data_dir, spec),
        classes=classes,
        feature_spec=spec,
    )
    metricas = evaluate(
        resultado.classifier,
        samples=_amostras(session, data_dir, spec, "val"),
        features_dir=features_dir(data_dir, spec),
    )
    info = log_run(
        tracking_uri=tracking_uri, experiment=experiment, config=config,
        result=resultado, metrics=metricas, register_as=model_name,
    )
    log.info("train.concluido", run_id=info.run_id, versao=info.model_version,
             val_macro_f1=round(metricas.macro_f1, 4))
    return info


def run_evaluate(
    session: Session,
    *,
    data_dir: Path,
    spec: FeatureSpec,
    tracking_uri: str,
    model_name: str,
    version: str,
    margin: float = 0.005,
    floor: float = 0.40,
) -> PromotionDecision:
    """Avalia no split de teste e aplica o gate. Não promover é sucesso, não erro."""
    classificador = carregar_versao(
        tracking_uri=tracking_uri, model_name=model_name, version=version, expected_spec=spec
    )
    desafiante = evaluate(
        classificador,
        samples=_amostras(session, data_dir, spec, "test"),
        features_dir=features_dir(data_dir, spec),
    )
    campeao = load_champion_metrics(tracking_uri=tracking_uri, model_name=model_name)
    decisao = should_promote(desafiante, campeao, margin=margin, floor=floor)

    if decisao.promote:
        promote(tracking_uri=tracking_uri, model_name=model_name, version=version)

    log.info("evaluate.concluido", promoveu=decisao.promote, motivo=decisao.reason,
             desafiante=round(decisao.challenger_f1, 4))
    return decisao
