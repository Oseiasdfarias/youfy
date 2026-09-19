from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Track


@dataclass(frozen=True, slots=True)
class LabeledTrackRow:
    track_id: str
    label: str


def labeled_tracks_for(session: Session, *, track_ids: list[str]) -> list[LabeledTrackRow]:
    """Traduz ids do catálogo em `(nome de arquivo de feature, rótulo)`.

    O `:` do id vira `_`, casando com o nome que o estágio `featurize` grava.
    """
    linhas = session.execute(
        select(Track.id, Track.top_genre)
        .where(Track.id.in_(track_ids))
        .where(Track.top_genre.is_not(None))
        .order_by(Track.id)
    ).all()
    return [LabeledTrackRow(tid.replace(":", "_"), genero) for tid, genero in linhas]


def known_genres(session: Session) -> list[str]:
    """Ordem canônica das classes: ordenada, para nunca depender de inserção."""
    linhas = session.execute(
        select(Track.top_genre).where(Track.top_genre.is_not(None)).distinct()
    ).scalars().all()
    return sorted(linhas)
