from __future__ import annotations

from pathlib import Path

import typer
from youfy_catalog.db import session_scope
from youfy_catalog.settings import Settings

from .ingest import run_ingest
from .logging import configure_logging

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
