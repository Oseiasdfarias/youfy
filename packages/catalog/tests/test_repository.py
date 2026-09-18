from youfy_catalog.models import Artist, IngestFailure, Track
from youfy_catalog.repository import record_failure, upsert_artist, upsert_track


def test_upsert_track_e_idempotente(session):
    upsert_artist(session, id="fma:artist:1", name="A", source="fma")
    for titulo in ("primeiro", "segundo"):
        upsert_track(session, id="fma:track:1", artist_id="fma:artist:1", title=titulo,
                     duration_ms=1000, audio_path="/x.wav", top_genre="Rock", source="fma")
    session.flush()
    assert session.query(Track).count() == 1
    assert session.get(Track, "fma:track:1").title == "segundo"

def test_upsert_artist_e_idempotente(session):
    for nome in ("A", "A renomeado"):
        upsert_artist(session, id="fma:artist:1", name=nome, source="fma")
    session.flush()
    assert session.query(Artist).count() == 1
    assert session.get(Artist, "fma:artist:1").name == "A renomeado"

def test_record_failure_persiste(session):
    record_failure(session, source_ref="fma:track:9", reason="unreadable_audio", detail="ruim")
    session.flush()
    assert session.query(IngestFailure).one().reason == "unreadable_audio"
