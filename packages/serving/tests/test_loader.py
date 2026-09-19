import pytest
from youfy_audio.spec import FeatureSpec
from youfy_serving.errors import FeatureSpecMismatch, NoProductionModel
from youfy_serving.loader import load_production

from .conftest import MODELO, SPEC


def test_carrega_o_modelo_sob_o_alias_de_producao(registry_com_campeao):
    uri, versao = registry_com_campeao
    carregado = load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)
    assert carregado.model_version == versao
    assert carregado.classifier.feature_spec == SPEC
    assert len(carregado.classifier.classes) == 8


def test_sem_modelo_promovido_levanta_erro_tipado(tmp_path):
    """Nunca chuta: a ausência de campeão é um estado nomeado."""
    uri = f"sqlite:///{tmp_path / 'vazio.db'}"
    with pytest.raises(NoProductionModel, match=MODELO):
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)


def test_feature_spec_divergente_recusa_carregar(registry_com_campeao):
    """Critério 9 da spec: training/serving skew vira falha na carga.

    Sem isto, um modelo treinado com n_mels=16 servido com 32 não estoura nem
    loga erro — só fica pior em silêncio.
    """
    uri, _ = registry_com_campeao
    divergente = FeatureSpec(n_mels=32, n_frames=20)
    with pytest.raises(FeatureSpecMismatch) as exc:
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=divergente)
    assert divergente.fingerprint() in str(exc.value)
    assert SPEC.fingerprint() in str(exc.value)


def test_divergencia_em_qualquer_campo_e_detectada(registry_com_campeao):
    uri, _ = registry_com_campeao
    for alterada in (
        FeatureSpec(n_mels=16, n_frames=20, hop_length=256),
        FeatureSpec(n_mels=16, n_frames=40),
        FeatureSpec(n_mels=16, n_frames=20, sample_rate=44100),
    ):
        with pytest.raises(FeatureSpecMismatch):
            load_production(tracking_uri=uri, model_name=MODELO, expected_spec=alterada)
