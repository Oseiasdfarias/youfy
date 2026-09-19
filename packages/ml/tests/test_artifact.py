# packages/ml/tests/test_artifact.py
import numpy as np
import pytest
from torch import nn
from youfy_audio.spec import FeatureSpec
from youfy_ml.artifact import GenreClassifier, TorchGenreClassifier

CLASSES = [
    "Electronic",
    "Folk",
    "Hip-Hop",
    "Instrumental",
    "International",
    "Pop",
    "Rock",
    "Experimental",
]


def _classificador(spec: FeatureSpec | None = None) -> TorchGenreClassifier:
    modulo = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(1, len(CLASSES)))
    return TorchGenreClassifier(
        module=modulo, feature_spec=spec or FeatureSpec(n_mels=16, n_frames=20), classes=CLASSES
    )


def test_satisfaz_o_protocolo():
    assert isinstance(_classificador(), GenreClassifier)


def test_predict_devolve_distribuicao_sobre_as_classes():
    clf = _classificador()
    dist = clf.predict(np.zeros((16, 20), dtype=np.float32))
    assert dist.shape == (len(CLASSES),)
    assert dist.dtype == np.float32
    assert np.isclose(dist.sum(), 1.0, atol=1e-5)
    assert (dist >= 0).all()


def test_roundtrip_preserva_feature_spec_e_classes(tmp_path):
    """A FeatureSpec viaja com o artefato; é o que impede training/serving skew."""
    spec = FeatureSpec(n_mels=64, n_frames=100, hop_length=256)
    original = _classificador(spec)
    original.save(tmp_path / "modelo")
    recarregado = TorchGenreClassifier.load(tmp_path / "modelo")

    assert recarregado.feature_spec == spec
    assert recarregado.feature_spec.fingerprint() == spec.fingerprint()
    assert recarregado.classes == CLASSES


def test_roundtrip_preserva_os_pesos(tmp_path):
    clf = _classificador()
    entrada = np.random.default_rng(0).normal(size=(16, 20)).astype(np.float32)
    antes = clf.predict(entrada)
    clf.save(tmp_path / "modelo")
    depois = TorchGenreClassifier.load(tmp_path / "modelo").predict(entrada)
    assert np.allclose(antes, depois, atol=1e-6)


def test_classes_vazias_sao_recusadas():
    with pytest.raises(ValueError, match="classes"):
        TorchGenreClassifier(module=nn.Identity(), feature_spec=FeatureSpec(), classes=[])


def test_predict_rejeita_shape_incompativel_com_a_spec():
    clf = _classificador(FeatureSpec(n_mels=16, n_frames=20))
    with pytest.raises(ValueError, match="shape"):
        clf.predict(np.zeros((32, 20), dtype=np.float32))
