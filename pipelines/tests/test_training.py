import json

from youfy_audio.spec import FeatureSpec
from youfy_catalog.queries import known_genres, labeled_tracks_for
from youfy_catalog.repository import upsert_artist, upsert_track
from youfy_pipelines.training import load_split

SPEC = FeatureSpec(n_mels=16, n_frames=20)


def _semear(session, n=6):
    upsert_artist(session, id="fma:artist:1", name="A", source="fma")
    for i in range(n):
        upsert_track(session, id=f"fma:track:{i}", artist_id="fma:artist:1", title=f"t{i}",
                     duration_ms=1000, audio_path=f"/x{i}.wav",
                     top_genre="Rock" if i % 2 else "Jazz", source="fma")
    session.flush()


def test_labeled_tracks_for_traduz_ids_em_rotulos(session):
    _semear(session)
    rotulados = labeled_tracks_for(session, track_ids=["fma:track:0", "fma:track:1"])
    assert {r.track_id for r in rotulados} == {"fma_track_0", "fma_track_1"}
    assert {r.label for r in rotulados} == {"Jazz", "Rock"}


def test_known_genres_e_ordenado_e_sem_repeticao(session):
    _semear(session)
    assert known_genres(session) == ["Jazz", "Rock"]


def test_known_genres_e_estavel_entre_chamadas(session):
    """A ordem das classes é contrato: instabilidade aqui reordena o vetor de saída."""
    _semear(session)
    assert known_genres(session) == known_genres(session)


def test_load_split_le_o_arquivo_do_fingerprint(tmp_path):
    destino = tmp_path / "splits" / SPEC.fingerprint()
    destino.mkdir(parents=True)
    (destino / "train.json").write_text(
        json.dumps({"seed": 42, "fingerprint": SPEC.fingerprint(),
                    "track_ids": ["fma:track:1", "fma:track:2"]})
    )
    assert load_split(tmp_path, SPEC, "train") == ["fma:track:1", "fma:track:2"]
