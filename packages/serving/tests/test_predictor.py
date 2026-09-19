import numpy as np
import pytest
from youfy_serving.loader import load_production
from youfy_serving.predictor import Predictor

from .conftest import MODELO, SPEC


@pytest.fixture
def preditor(registry_com_campeao):
    uri, _ = registry_com_campeao
    return Predictor(load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC))


def test_predicao_traz_distribuicao_normalizada_sobre_as_classes(preditor):
    p = preditor.predict(np.zeros((16, 20), dtype=np.float32))
    assert len(p.distribution) == 8
    assert np.isclose(sum(p.distribution.values()), 1.0, atol=1e-5)


def test_predicao_carrega_a_versao_do_modelo(preditor, registry_com_campeao):
    _, versao = registry_com_campeao
    assert preditor.predict(np.zeros((16, 20), dtype=np.float32)).model_version == versao


def test_top_genre_e_o_argmax_da_distribuicao(preditor):
    p = preditor.predict(np.zeros((16, 20), dtype=np.float32))
    assert p.top_genre == max(p.distribution, key=p.distribution.get)


def test_melspec_com_shape_errado_e_recusado(preditor):
    with pytest.raises(ValueError, match="shape"):
        preditor.predict(np.zeros((32, 20), dtype=np.float32))
