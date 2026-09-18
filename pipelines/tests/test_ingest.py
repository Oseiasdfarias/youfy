import pytest
from youfy_catalog.models import IngestFailure, Track
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_pipelines.ingest import run_ingest


def test_ingere_faixas_validas_e_quarentena_as_corrompidas(session, tmp_path):
    build_fma_fixture(tmp_path, [
        FixtureTrack(2, 10, "Artista A", "Rock"),
        FixtureTrack(3, 10, "Artista A", "Rock"),
        FixtureTrack(1005, 11, "Artista B", "Jazz", corrompido=True),
    ])
    relatorio = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()

    assert relatorio.total == 3
    assert relatorio.ingested == 2
    assert relatorio.failed == 1
    assert session.query(Track).count() == 2
    assert session.query(IngestFailure).one().reason == "unreadable_audio"


def test_arquivo_ausente_vira_quarentena_e_nao_excecao(session, tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", "Rock")])
    (tmp_path / "fma_small" / "000" / "000002.wav").unlink()
    relatorio = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert relatorio.ingested == 0
    assert session.query(IngestFailure).one().reason == "unreadable_audio"


def test_faixa_sem_genero_top_vira_quarentena(session, tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", genre_top=None)])
    relatorio = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert relatorio.ingested == 0
    assert session.query(IngestFailure).one().reason == "missing_genre"


def test_reexecucao_e_idempotente(session, tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", "Rock")])
    for _ in range(2):
        run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert session.query(Track).count() == 1


def test_taxa_de_falha_e_calculada():
    from youfy_pipelines.ingest import IngestReport
    assert IngestReport(total=100, ingested=97, failed=3).failure_rate == pytest.approx(0.03)
    assert IngestReport(total=0, ingested=0, failed=0).failure_rate == 0.0
