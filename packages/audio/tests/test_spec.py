from youfy_audio.spec import FeatureSpec


def test_fingerprint_e_estavel_entre_instancias_iguais():
    assert FeatureSpec().fingerprint() == FeatureSpec().fingerprint()


def test_fingerprint_muda_quando_qualquer_campo_muda():
    base = FeatureSpec()
    assert FeatureSpec(n_mels=96).fingerprint() != base.fingerprint()
    assert FeatureSpec(hop_length=256).fingerprint() != base.fingerprint()


def test_fmax_efetivo_default_e_nyquist():
    assert FeatureSpec().effective_fmax == 22050 / 2
