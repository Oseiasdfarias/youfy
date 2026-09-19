"""Fecha o ciclo: acervo → features → split → treino → gate → serving.

É o teste que prova que os artefatos do 1A alimentam o 1B sem adaptador.
"""
import numpy as np
import pytest
from youfy_audio.spec import FeatureSpec
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_ml.train import TrainConfig
from youfy_pipelines.featurize import run_featurize
from youfy_pipelines.ingest import run_ingest
from youfy_pipelines.split import run_split
from youfy_pipelines.training import run_evaluate, run_train
from youfy_serving.errors import FeatureSpecMismatch, NoProductionModel
from youfy_serving.loader import load_production
from youfy_serving.predictor import Predictor

SPEC = FeatureSpec(n_mels=16, n_frames=20)
MODELO = "youfy-genre-clf"
GENEROS = ["Rock", "Jazz", "Folk"]

# O e2e passa `floor=0.0` de proposito: a promocao precisa ser deterministica
# para que as assercoes seguintes sempre rodem. O piso e a margem tem cobertura
# exaustiva na Task 6, onde sao funcao pura.
PISO_E2E = 0.0


@pytest.fixture
def acervo(session, tmp_path):
    faixas = []
    tid = 2
    for g, genero in enumerate(GENEROS):
        for a in range(10):
            for _ in range(3):
                faixas.append(FixtureTrack(tid, g * 100 + a, f"Artista {g}-{a}", genero))
                tid += 1
    build_fma_fixture(tmp_path, faixas)
    run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    run_featurize(session, data_dir=tmp_path / "data", spec=SPEC)
    session.flush()
    run_split(session, data_dir=tmp_path / "data", spec=SPEC, seed=42)
    return tmp_path / "data", f"sqlite:///{tmp_path / 'mlflow.db'}"


def test_serving_antes_do_primeiro_treino_recusa_de_forma_tipada(acervo):
    _, uri = acervo
    with pytest.raises(NoProductionModel):
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)


def test_ciclo_completo_treina_promove_e_serve(session, acervo):
    data_dir, uri = acervo

    info = run_train(
        session, data_dir=data_dir, spec=SPEC,
        config=TrainConfig(seed=0, epochs=3, batch_size=8),
        tracking_uri=uri, model_name=MODELO, experiment="e2e",
    )
    assert info.model_version is not None

    decisao = run_evaluate(
        session, data_dir=data_dir, spec=SPEC, tracking_uri=uri,
        model_name=MODELO, version=info.model_version, floor=PISO_E2E,
    )
    assert decisao.champion_f1 is None  # primeiro modelo: o criterio e o piso
    assert decisao.promote is True

    preditor = Predictor(
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)
    )
    p = preditor.predict(np.zeros((16, 20), dtype=np.float32))
    assert p.model_version == info.model_version
    assert set(p.distribution) == set(GENEROS)
    assert np.isclose(sum(p.distribution.values()), 1.0, atol=1e-5)


def test_featurizer_divergente_derruba_o_serving_na_carga(session, acervo):
    """Critério 9 no encadeamento real, não só no unitário."""
    data_dir, uri = acervo
    info = run_train(
        session, data_dir=data_dir, spec=SPEC,
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        tracking_uri=uri, model_name=MODELO, experiment="e2e",
    )
    decisao = run_evaluate(
        session, data_dir=data_dir, spec=SPEC, tracking_uri=uri,
        model_name=MODELO, version=info.model_version, floor=PISO_E2E,
    )
    assert decisao.promote is True

    with pytest.raises(FeatureSpecMismatch):
        load_production(
            tracking_uri=uri, model_name=MODELO,
            expected_spec=FeatureSpec(n_mels=32, n_frames=20),
        )
