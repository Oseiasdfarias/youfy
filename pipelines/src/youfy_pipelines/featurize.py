from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from youfy_audio.decode import decode
from youfy_audio.errors import UnreadableAudio
from youfy_audio.melspec import compute_melspec
from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Feature, Track

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class FeaturizeReport:
    total: int
    computed: int
    skipped: int
    failed: int


def features_dir(data_dir: Path, spec: FeatureSpec) -> Path:
    return data_dir / "features" / "melspec" / spec.fingerprint()


def write_manifest(destino: Path, spec: FeatureSpec) -> None:
    (destino / "_manifest.json").write_text(
        json.dumps({"fingerprint": spec.fingerprint(), "spec": asdict(spec)}, indent=2)
    )


def _nome_arquivo(track_id: str) -> str:
    return track_id.replace(":", "_") + ".npy"


def run_featurize(session: Session, *, data_dir: Path, spec: FeatureSpec) -> FeaturizeReport:
    destino = features_dir(data_dir, spec)
    destino.mkdir(parents=True, exist_ok=True)
    write_manifest(destino, spec)

    faixas = session.execute(select(Track)).scalars().all()
    computadas = puladas = falhas = 0

    for faixa in faixas:
        arquivo = destino / _nome_arquivo(faixa.id)
        # A presença do arquivo é o sinal de retomada: sem estado extra para
        # dessincronizar, e seguro contra interrupção no meio de 8 mil faixas.
        if arquivo.exists():
            puladas += 1
            continue

        try:
            samples = decode(faixa.audio_path, target_sample_rate=spec.sample_rate)
            mel = compute_melspec(samples, spec.sample_rate, spec)
        except UnreadableAudio as exc:
            _registrar_feature(
                session, faixa.id, spec, path=None, status="failed", detail=str(exc)
            )
            falhas += 1
            continue

        np.save(arquivo, mel)
        _registrar_feature(
            session, faixa.id, spec, path=str(arquivo), status="ok", detail=None
        )
        computadas += 1

    relatorio = FeaturizeReport(len(faixas), computadas, puladas, falhas)
    log.info(
        "featurize.concluido",
        fingerprint=spec.fingerprint(),
        total=relatorio.total,
        computadas=computadas,
        puladas=puladas,
        falhas=falhas,
    )
    return relatorio


def _registrar_feature(
    session: Session,
    track_id: str,
    spec: FeatureSpec,
    *,
    path: str | None,
    status: str,
    detail: str | None,
) -> None:
    stmt = insert(Feature).values(
        track_id=track_id,
        spec_fingerprint=spec.fingerprint(),
        path=path,
        status=status,
        detail=detail,
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["track_id", "spec_fingerprint"],
            set_={"path": path, "status": status, "detail": detail},
        )
    )
