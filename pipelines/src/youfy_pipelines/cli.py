from __future__ import annotations

from pathlib import Path

import typer
from youfy_audio.spec import FeatureSpec
from youfy_catalog.db import session_scope
from youfy_catalog.settings import Settings
from youfy_ml.train import TrainConfig

from .featurize import run_featurize
from .ingest import run_ingest
from .logging import configure_logging
from .split import run_split
from .training import run_evaluate, run_train

app = typer.Typer(help="Youfy — pipelines de dados e treino.")
pipeline = typer.Typer(help="Estágios do pipeline offline.")
app.add_typer(pipeline, name="pipeline")


@pipeline.command("ingest")
def ingest_cmd(
    dump_dir: Path = typer.Option(None, help="Raiz do dump do FMA."),  # noqa: B008
    subset: str = typer.Option("small"),
    audio_ext: str = typer.Option(".mp3"),
    max_failure_rate: float = typer.Option(0.02, help="Acima disso, sai com erro."),
) -> None:
    configure_logging()
    raiz = dump_dir or Settings().fma_dump_dir
    with session_scope() as session:
        relatorio = run_ingest(session, dump_dir=raiz, subset=subset, audio_ext=audio_ext)

    typer.echo(
        f"total={relatorio.total} ingeridas={relatorio.ingested} "
        f"falhas={relatorio.failed} taxa={relatorio.failure_rate:.4f}"
    )
    if relatorio.failure_rate > max_failure_rate:
        typer.echo(
            f"ERRO: taxa de falha {relatorio.failure_rate:.4f} acima do limite "
            f"{max_failure_rate:.4f}",
            err=True,
        )
        raise typer.Exit(code=1)


@pipeline.command("featurize")
def featurize_cmd(
    data_dir: Path = typer.Option(None),  # noqa: B008
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
) -> None:
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    with session_scope() as session:
        relatorio = run_featurize(session, data_dir=raiz, spec=spec)
    typer.echo(
        f"fingerprint={spec.fingerprint()} total={relatorio.total} "
        f"computadas={relatorio.computed} puladas={relatorio.skipped} "
        f"falhas={relatorio.failed}"
    )


@pipeline.command("split")
def split_cmd(
    data_dir: Path = typer.Option(None),  # noqa: B008
    seed: int = typer.Option(42),
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
) -> None:
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    with session_scope() as session:
        splits = run_split(session, data_dir=raiz, spec=spec, seed=seed)
    typer.echo(
        f"train={len(splits.train)} val={len(splits.val)} test={len(splits.test)}"
    )


@pipeline.command("train")
def train_cmd(
    data_dir: Path = typer.Option(None),  # noqa: B008
    seed: int = typer.Option(42),
    epochs: int = typer.Option(10),
    batch_size: int = typer.Option(32),
    lr: float = typer.Option(1e-3),
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
    tracking_uri: str = typer.Option("http://localhost:5000"),
    model_name: str = typer.Option("youfy-genre-clf"),
) -> None:
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    config = TrainConfig(seed=seed, epochs=epochs, batch_size=batch_size, lr=lr)
    with session_scope() as session:
        info = run_train(session, data_dir=raiz, spec=spec, config=config,
                         tracking_uri=tracking_uri, model_name=model_name)
    typer.echo(f"run_id={info.run_id} versao={info.model_version}")


@pipeline.command("evaluate")
def evaluate_cmd(
    version: str = typer.Option(..., help="Versao registrada a avaliar."),
    data_dir: Path = typer.Option(None),  # noqa: B008
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
    tracking_uri: str = typer.Option("http://localhost:5000"),
    model_name: str = typer.Option("youfy-genre-clf"),
    margin: float = typer.Option(0.005),
    floor: float = typer.Option(0.40),
) -> None:
    """Nao promover e resultado valido: sai com codigo 0 e relata o motivo."""
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    with session_scope() as session:
        decisao = run_evaluate(session, data_dir=raiz, spec=spec, tracking_uri=tracking_uri,
                                model_name=model_name, version=version,
                                margin=margin, floor=floor)
    typer.echo(f"promoveu={decisao.promote} motivo={decisao.reason}")


