from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog
from sqlalchemy.orm import Session
from youfy_audio.decode import probe
from youfy_audio.errors import UnreadableAudio
from youfy_catalog.fma import audio_path_for, read_tracks_csv
from youfy_catalog.repository import record_failure, upsert_artist, upsert_track

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class IngestReport:
    total: int
    ingested: int
    failed: int

    @property
    def failure_rate(self) -> float:
        return self.failed / self.total if self.total else 0.0


def run_ingest(
    session: Session,
    *,
    dump_dir: Path,
    subset: str = "small",
    audio_ext: str = ".mp3",
) -> IngestReport:
    """Falha de dado vira quarentena; a execução nunca para por causa de uma faixa."""
    linhas = read_tracks_csv(dump_dir / "fma_metadata" / "tracks.csv", subset=subset)
    audio_root = dump_dir / f"fma_{subset}"
    ingeridas = falhas = 0

    for linha in linhas:
        ref = f"fma:track:{linha.track_id}"
        if linha.genre_top is None:
            record_failure(session, source_ref=ref, reason="missing_genre", detail=None)
            falhas += 1
            continue

        caminho = audio_path_for(linha.track_id, audio_root, ext=audio_ext)
        try:
            info = probe(caminho)
        except UnreadableAudio as exc:
            record_failure(session, source_ref=ref, reason="unreadable_audio", detail=str(exc))
            falhas += 1
            continue

        artist_id = f"fma:artist:{linha.artist_id}"
        upsert_artist(session, id=artist_id, name=linha.artist_name, source="fma")
        upsert_track(
            session,
            id=ref,
            artist_id=artist_id,
            title=linha.title,
            duration_ms=int(info.duration_s * 1000),
            audio_path=str(caminho),
            top_genre=linha.genre_top,
            source="fma",
        )
        ingeridas += 1

    relatorio = IngestReport(total=len(linhas), ingested=ingeridas, failed=falhas)
    log.info(
        "ingest.concluido",
        total=relatorio.total,
        ingeridas=ingeridas,
        falhas=falhas,
        taxa_de_falha=round(relatorio.failure_rate, 4),
    )
    return relatorio
