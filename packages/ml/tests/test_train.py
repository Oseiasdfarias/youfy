# packages/ml/tests/test_train.py
import pytest
from youfy_audio.spec import FeatureSpec
from youfy_ml.testing import escrever_features
from youfy_ml.train import TrainConfig, train

SPEC = FeatureSpec(n_mels=16, n_frames=20)


def _treinar(tmp_path, *, seed=42, epochs=8, embaralhar=False, por_classe=24):
    amostras, classes = escrever_features(
        tmp_path,
        n_classes=8,
        por_classe=por_classe,
        n_mels=16,
        n_frames=20,
        seed=0,
        embaralhar_rotulos=embaralhar,
    )
    corte = int(len(amostras) * 0.75)
    return train(
        TrainConfig(seed=seed, epochs=epochs, batch_size=16),
        train_samples=amostras[:corte],
        val_samples=amostras[corte:],
        features_dir=tmp_path,
        classes=classes,
        feature_spec=SPEC,
    )


def test_treina_e_devolve_classificador_com_a_spec_embutida(tmp_path):
    r = _treinar(tmp_path)
    assert r.classifier.feature_spec == SPEC
    assert len(r.classifier.classes) == 8
    assert len(r.history) == 8


def test_aprende_sinal_presente_no_dado(tmp_path):
    """Sanidade: com sinal aprendível, a acurácia de validação sai do acaso (0,125)."""
    r = _treinar(tmp_path, epochs=12)
    assert r.history[-1].val_acc > 0.5


def test_reprodutibilidade_mesma_seed_mesmo_resultado(tmp_path):
    """Critério 11 da spec. Falhar aqui significa não-determinismo escondido."""
    a = _treinar(tmp_path, seed=7)
    b = _treinar(tmp_path, seed=7)
    assert abs(a.history[-1].val_acc - b.history[-1].val_acc) <= 0.002
    assert abs(a.history[-1].train_loss - b.history[-1].train_loss) <= 0.002


def test_seeds_diferentes_divergem(tmp_path):
    a = _treinar(tmp_path, seed=1, epochs=4)
    b = _treinar(tmp_path, seed=999, epochs=4)
    assert a.history[-1].train_loss != b.history[-1].train_loss


def test_overfit_proposital_em_50_amostras(tmp_path):
    """Separa 'o modelo é ruim' de 'o pipeline de dado está quebrado'.

    Com ruído puro e rótulos arbitrários, um pipeline sadio ainda memoriza.
    Se isto falhar, o defeito está no fluxo de dados, não na arquitetura.
    """
    amostras, classes = escrever_features(
        tmp_path, n_classes=8, por_classe=7, n_mels=16, n_frames=20, seed=3
    )
    amostras = amostras[:50]
    r = train(
        TrainConfig(seed=0, epochs=120, batch_size=10, lr=3e-3),
        train_samples=amostras,
        val_samples=amostras,
        features_dir=tmp_path,
        classes=classes,
        feature_spec=SPEC,
    )
    assert r.final_train_acc >= 0.95


def test_num_workers_maior_que_zero_e_recusado_com_determinismo(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=2)
    with pytest.raises(ValueError, match="num_workers"):
        train(
            TrainConfig(num_workers=2),
            train_samples=amostras,
            val_samples=amostras,
            features_dir=tmp_path,
            classes=classes,
            feature_spec=SPEC,
        )
