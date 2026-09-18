from pathlib import Path

from youfy_catalog.fma import audio_path_for, read_tracks_csv
from youfy_catalog.testing import FixtureTrack, build_fma_fixture


def test_le_o_cabecalho_de_dois_niveis_do_tracks_csv(tmp_path):
    build_fma_fixture(tmp_path, [
        FixtureTrack(2, 10, "Artista A", "Rock"),
        FixtureTrack(1005, 11, "Artista B", "Jazz"),
    ])
    linhas = read_tracks_csv(tmp_path / "fma_metadata" / "tracks.csv")
    assert {l.track_id for l in linhas} == {2, 1005}
    assert {l.genre_top for l in linhas} == {"Rock", "Jazz"}
    assert {l.artist_name for l in linhas} == {"Artista A", "Artista B"}

def test_filtra_por_subset(tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", "Rock")])
    assert len(read_tracks_csv(tmp_path / "fma_metadata" / "tracks.csv", subset="small")) == 1
    assert read_tracks_csv(tmp_path / "fma_metadata" / "tracks.csv", subset="large") == []

def test_caminho_de_audio_usa_o_particionamento_por_milhar():
    raiz = Path("/dados/fma_small")
    assert audio_path_for(2, raiz, ext=".mp3") == raiz / "000" / "000002.mp3"
    assert audio_path_for(1005, raiz, ext=".wav") == raiz / "001" / "001005.wav"
