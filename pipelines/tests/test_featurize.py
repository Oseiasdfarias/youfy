import json

import numpy as np
from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Feature
from youfy_catalog.repository import upsert_artist, upsert_track
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_pipelines.featurize import features_dir, run_featurize


def _acervo(session, tmp_path, ids=(2, 3)):
    faixas = [FixtureTrack(i, 10, "A", "Rock") for i in ids]
    build_fma_fixture(tmp_path, faixas)
    upsert_artist(session, id="fma:artist:10", name="A", source="fma")
    for i in ids:
        caminho = tmp_path / "fma_small" / f"{i // 1000:03d}" / f"{i:06d}.wav"
        upsert_track(
            session,
            id=f"fma:track:{i}",
            artist_id="fma:artist:10",
            title=f"t{i}",
            duration_ms=1000,
            audio_path=str(caminho),
            top_genre="Rock",
            source="fma",
        )
    session.flush()


def test_gera_um_npy_por_faixa_com_o_shape_da_spec(session, tmp_path):
    _acervo(session, tmp_path)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    relatorio = run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    session.flush()

    assert relatorio.computed == 2
    destino = features_dir(tmp_path / "data", spec)
    arr = np.load(destino / "fma_track_2.npy")
    assert arr.shape == (32, 40)
    assert arr.dtype == np.float32
    assert session.query(Feature).filter_by(status="ok").count() == 2


def test_reexecucao_pula_o_que_ja_existe(session, tmp_path):
    _acervo(session, tmp_path)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    session.flush()
    segunda = run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    assert segunda.computed == 0
    assert segunda.skipped == 2


def test_config_diferente_gera_diretorio_novo_sem_apagar_o_anterior(session, tmp_path):
    _acervo(session, tmp_path)
    antiga = FeatureSpec(n_mels=32, n_frames=40)
    nova = FeatureSpec(n_mels=16, n_frames=40)
    run_featurize(session, data_dir=tmp_path / "data", spec=antiga)
    run_featurize(session, data_dir=tmp_path / "data", spec=nova)
    session.flush()
    assert (features_dir(tmp_path / "data", antiga) / "fma_track_2.npy").exists()
    assert (features_dir(tmp_path / "data", nova) / "fma_track_2.npy").exists()


def test_audio_ilegivel_vira_feature_failed_sem_derrubar(session, tmp_path):
    _acervo(session, tmp_path, ids=(2, 3))
    (tmp_path / "fma_small" / "000" / "000003.wav").write_bytes(b"RIFF" + b"\x00lixo" * 40)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    relatorio = run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    session.flush()
    assert relatorio.computed == 1
    assert relatorio.failed == 1
    assert session.query(Feature).filter_by(status="failed").count() == 1


def test_manifest_registra_a_spec(session, tmp_path):
    _acervo(session, tmp_path)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    manifesto = json.loads((features_dir(tmp_path / "data", spec) / "_manifest.json").read_text())
    assert manifesto["fingerprint"] == spec.fingerprint()
    assert manifesto["spec"]["n_mels"] == 32
