import pytest
from sqlalchemy.exc import IntegrityError
from youfy_catalog.models import Artist, Feature, Genre, IngestFailure, Track, TrackGenre


def _artista(session, ident="fma:artist:1"):
    a = Artist(id=ident, name="Banda Teste", source="fma")
    session.add(a)
    session.flush()
    return a

def test_track_exige_artista_existente(session):
    session.add(Track(id="fma:track:1", artist_id="fma:artist:inexistente",
                      title="t", duration_ms=1000, audio_path="/x.wav", source="fma"))
    with pytest.raises(IntegrityError):
        session.flush()

def test_track_persiste_com_genero_top(session):
    _artista(session)
    session.add(Track(id="fma:track:1", artist_id="fma:artist:1", title="t",
                      duration_ms=30000, audio_path="/x.wav", top_genre="Rock", source="fma"))
    session.flush()
    assert session.get(Track, "fma:track:1").top_genre == "Rock"

def test_track_genre_e_unico_por_par(session):
    _artista(session)
    session.add_all([
        Track(id="fma:track:1", artist_id="fma:artist:1", title="t",
              duration_ms=1, audio_path="/x.wav", source="fma"),
        Genre(id=12, name="Rock", parent_id=None),
    ])
    session.flush()
    session.add(TrackGenre(track_id="fma:track:1", genre_id=12))
    session.flush()
    session.add(TrackGenre(track_id="fma:track:1", genre_id=12))
    with pytest.raises(IntegrityError):
        session.flush()

def test_ingest_failure_registra_motivo(session):
    session.add(IngestFailure(source_ref="fma:track:99", reason="unreadable_audio",
                              detail="cabecalho invalido"))
    session.flush()
    assert session.query(IngestFailure).count() == 1

def test_feature_e_unica_por_track_e_fingerprint(session):
    _artista(session)
    session.add(Track(id="fma:track:1", artist_id="fma:artist:1", title="t",
                      duration_ms=1, audio_path="/x.wav", source="fma"))
    session.flush()
    session.add(Feature(track_id="fma:track:1", spec_fingerprint="abc123",
                        path="/f.npy", status="ok"))
    session.flush()
    session.add(Feature(track_id="fma:track:1", spec_fingerprint="abc123",
                        path="/outro.npy", status="ok"))
    with pytest.raises(IntegrityError):
        session.flush()
