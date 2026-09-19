import numpy as np
import pytest
import torch
from youfy_ml.dataset import LabeledTrack, MelspecDataset, MissingFeature
from youfy_ml.testing import escrever_features


def test_devolve_tensor_com_canal_e_indice_da_classe(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=2, n_mels=16, n_frames=20)
    ds = MelspecDataset(amostras, features_dir=tmp_path, classes=classes)
    x, y = ds[0]
    assert isinstance(x, torch.Tensor)
    assert x.shape == (1, 16, 20)
    assert x.dtype == torch.float32
    assert 0 <= int(y) < len(classes)


def test_tamanho_bate_com_as_amostras(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=3)
    assert len(MelspecDataset(amostras, features_dir=tmp_path, classes=classes)) == 24


def test_indice_da_classe_segue_a_ordem_canonica(tmp_path):
    """A ordem das classes é contrato; não pode depender da ordem das amostras."""
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=1)
    ds = MelspecDataset(amostras, features_dir=tmp_path, classes=classes)
    for i, amostra in enumerate(amostras):
        _, y = ds[i]
        assert int(y) == classes.index(amostra.label)


def test_feature_ausente_levanta_erro_nomeando_a_faixa(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=1)
    (tmp_path / f"{amostras[0].track_id}.npy").unlink()
    ds = MelspecDataset(amostras, features_dir=tmp_path, classes=classes)
    with pytest.raises(MissingFeature, match=amostras[0].track_id):
        _ = ds[0]


def test_rotulo_fora_das_classes_e_recusado_na_construcao(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=1)
    intruso = [*amostras, LabeledTrack("fma_track_x", "GeneroInexistente")]
    with pytest.raises(ValueError, match="GeneroInexistente"):
        MelspecDataset(intruso, features_dir=tmp_path, classes=classes)


def test_leitura_e_deterministica(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=2)
    ds = MelspecDataset(amostras, features_dir=tmp_path, classes=classes)
    a, _ = ds[5]
    b, _ = ds[5]
    assert torch.equal(a, b)
    assert np.array_equal(a.numpy(), b.numpy())
