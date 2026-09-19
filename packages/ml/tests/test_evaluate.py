from youfy_audio.spec import FeatureSpec
from youfy_ml.evaluate import evaluate
from youfy_ml.testing import escrever_features
from youfy_ml.train import TrainConfig, train

SPEC = FeatureSpec(n_mels=16, n_frames=20)


def _treinar(tmp_path, *, embaralhar: bool, epochs: int = 15, seed: int = 5):
    amostras, classes = escrever_features(
        tmp_path, n_classes=8, por_classe=24, n_mels=16, n_frames=20,
        seed=1, embaralhar_rotulos=embaralhar,
    )
    corte = int(len(amostras) * 0.75)
    r = train(
        TrainConfig(seed=seed, epochs=epochs, batch_size=16),
        train_samples=amostras[:corte], val_samples=amostras[corte:],
        features_dir=tmp_path, classes=classes, feature_spec=SPEC,
    )
    return r, amostras[corte:], classes


def test_metricas_tem_a_forma_esperada(tmp_path):
    r, teste, classes = _treinar(tmp_path, embaralhar=False)
    m = evaluate(r.classifier, samples=teste, features_dir=tmp_path)
    assert 0.0 <= m.macro_f1 <= 1.0
    assert 0.0 <= m.accuracy <= 1.0
    assert set(m.per_class_f1) == set(classes)
    assert len(m.confusion) == len(classes)
    assert all(len(linha) == len(classes) for linha in m.confusion)


def test_as_flat_dict_e_serializavel_para_o_mlflow(tmp_path):
    r, teste, _ = _treinar(tmp_path, embaralhar=False, epochs=4)
    plano = evaluate(r.classifier, samples=teste, features_dir=tmp_path).as_flat_dict()
    assert "macro_f1" in plano and "accuracy" in plano
    assert all(isinstance(v, float) for v in plano.values())


def test_com_sinal_real_supera_o_acaso(tmp_path):
    r, teste, _ = _treinar(tmp_path, embaralhar=False)
    assert evaluate(r.classifier, samples=teste, features_dir=tmp_path).macro_f1 > 0.40


def test_rotulos_embaralhados_ficam_na_faixa_do_acaso(tmp_path):
    """Critério 12 da spec. Passar deste limiar significa vazamento.

    São 8 classes balanceadas: acaso = 0,125, limiar = 0,20.
    """
    r, teste, _ = _treinar(tmp_path, embaralhar=True)
    assert evaluate(r.classifier, samples=teste, features_dir=tmp_path).macro_f1 <= 0.20
