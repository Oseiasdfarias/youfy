from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import Artist, IngestFailure, Track


def upsert_artist(session: Session, *, id: str, name: str, source: str) -> None:
    stmt = insert(Artist).values(id=id, name=name, source=source)
    session.execute(
        stmt.on_conflict_do_update(index_elements=["id"], set_={"name": name, "source": source})
    )

def upsert_track(
    session: Session,
    *,
    id: str,
    artist_id: str,
    title: str,
    duration_ms: int,
    audio_path: str,
    source: str,
    top_genre: str | None = None,
) -> None:
    valores = {
        "id": id,
        "artist_id": artist_id,
        "title": title,
        "duration_ms": duration_ms,
        "audio_path": audio_path,
        "top_genre": top_genre,
        "source": source,
    }
    stmt = insert(Track).values(**valores)
    atualizaveis = {k: v for k, v in valores.items() if k != "id"}
    session.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=atualizaveis))

def record_failure(session: Session, *, source_ref: str, reason: str, detail: str | None) -> None:
    session.add(IngestFailure(source_ref=source_ref, reason=reason, detail=detail))
