import mlflow
import pytest
from mlflow.tracking import MlflowClient
from youfy_audio.spec import FeatureSpec
from youfy_ml.evaluate import Metrics
from youfy_ml.testing import escrever_features
from youfy_ml.tracking import ALIAS_PRODUCAO, load_champion_metrics, log_run, promote
from youfy_ml.train import TrainConfig, train

SPEC = FeatureSpec(n_mels=16, n_frames=20)
MODELO = "youfy-genre-clf"


@pytest.fixture
def tracking_uri(tmp_path):
    return f"sqlite:///{tmp_path / 'mlflow.db'}"


@pytest.fixture
def resultado(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=4, n_mels=16, n_frames=20)
    return train(
        TrainConfig(seed=0, epochs=2, batch_size=8),
        train_samples=amostras, val_samples=amostras,
        features_dir=tmp_path, classes=classes, feature_spec=SPEC,
    )


def _metricas(f1: float) -> Metrics:
    return Metrics(macro_f1=f1, accuracy=f1, per_class_f1={"g0": f1}, confusion=[[1]])


def test_log_run_registra_params_metricas_e_artefato(tracking_uri, resultado):
    info = log_run(
        tracking_uri=tracking_uri, experiment="teste",
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        result=resultado, metrics=_metricas(0.7), register_as=MODELO,
    )
    mlflow.set_tracking_uri(tracking_uri)
    run = MlflowClient().get_run(info.run_id)
    assert run.data.params["seed"] == "0"
    assert run.data.params["epochs"] == "2"
    assert run.data.metrics["macro_f1"] == pytest.approx(0.7)
    assert info.model_version is not None


def test_log_run_registra_a_curva_de_treino_por_epoca(tracking_uri, resultado):
    info = log_run(
        tracking_uri=tracking_uri, experiment="teste",
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        result=resultado, metrics=_metricas(0.7), register_as=MODELO,
    )
    mlflow.set_tracking_uri(tracking_uri)
    historico = MlflowClient().get_metric_history(info.run_id, "train_loss")
    assert len(historico) == 2


def test_sem_alias_nao_ha_campeao(tracking_uri):
    assert load_champion_metrics(tracking_uri=tracking_uri, model_name=MODELO) is None


def test_promove_e_le_as_metricas_do_campeao(tracking_uri, resultado):
    info = log_run(
        tracking_uri=tracking_uri, experiment="teste",
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        result=resultado, metrics=_metricas(0.63), register_as=MODELO,
    )
    promote(tracking_uri=tracking_uri, model_name=MODELO, version=info.model_version)
    campeao = load_champion_metrics(tracking_uri=tracking_uri, model_name=MODELO)
    assert campeao is not None
    assert campeao.macro_f1 == pytest.approx(0.63)


def test_promover_move_o_alias_para_a_nova_versao(tracking_uri, resultado):
    cfg = TrainConfig(seed=0, epochs=2, batch_size=8)
    primeira = log_run(tracking_uri=tracking_uri, experiment="t", config=cfg,
                       result=resultado, metrics=_metricas(0.50), register_as=MODELO)
    promote(tracking_uri=tracking_uri, model_name=MODELO, version=primeira.model_version)
    segunda = log_run(tracking_uri=tracking_uri, experiment="t", config=cfg,
                      result=resultado, metrics=_metricas(0.80), register_as=MODELO)
    promote(tracking_uri=tracking_uri, model_name=MODELO, version=segunda.model_version)

    mlflow.set_tracking_uri(tracking_uri)
    vigente = MlflowClient().get_model_version_by_alias(MODELO, ALIAS_PRODUCAO)
    assert vigente.version == segunda.model_version
    assert load_champion_metrics(
        tracking_uri=tracking_uri, model_name=MODELO
    ).macro_f1 == pytest.approx(0.80)
