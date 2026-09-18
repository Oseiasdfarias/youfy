from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _agora() -> datetime:
    return datetime.now(UTC)

class Base(DeclarativeBase):
    pass

class Artist(Base):
    __tablename__ = "artists"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)

class Genre(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    artist_id: Mapped[str] = mapped_column(ForeignKey("artists.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    audio_path: Mapped[str] = mapped_column(Text, nullable=False)
    top_genre: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class TrackGenre(Base):
    __tablename__ = "track_genres"
    __table_args__ = (UniqueConstraint("track_id", "genre_id", name="uq_track_genre"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), nullable=False)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"), nullable=False)

class IngestFailure(Base):
    __tablename__ = "ingest_failures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class Feature(Base):
    """Uma linha por (faixa, fingerprint de FeatureSpec).

    Guardar o fingerprint permite que features de configs diferentes coexistam
    sem que uma invalide a outra por deleção.
    """

    __tablename__ = "features"
    __table_args__ = (
        UniqueConstraint("track_id", "spec_fingerprint", name="uq_feature_track_spec"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), nullable=False, index=True)
    spec_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # ok | failed
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
