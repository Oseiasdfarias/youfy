import librosa
import numpy as np
import pytest
from youfy_audio.melspec import compute_melspec
from youfy_audio.spec import FeatureSpec


def _seno(freq: float, segundos: float, sr: int) -> np.ndarray:
    t = np.linspace(0.0, segundos, int(sr * segundos), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def test_seno_de_440hz_tem_pico_no_bin_correspondente():
    spec = FeatureSpec()
    mel_db = compute_melspec(_seno(440.0, 2.0, spec.sample_rate), spec.sample_rate, spec)
    bin_pico = int(np.argmax(mel_db.mean(axis=1)))
    centros = librosa.mel_frequencies(
        n_mels=spec.n_mels, fmin=spec.fmin, fmax=spec.effective_fmax
    )
    assert abs(centros[bin_pico] - 440.0) < 60.0


def test_silencio_fica_no_piso_de_db():
    spec = FeatureSpec()
    mel_db = compute_melspec(np.zeros(spec.sample_rate, dtype=np.float32), spec.sample_rate, spec)
    assert np.allclose(mel_db, mel_db.min())


def test_shape_e_dtype_sao_determinados_pela_spec():
    spec = FeatureSpec(n_mels=64, n_frames=100)
    mel_db = compute_melspec(_seno(440.0, 5.0, spec.sample_rate), spec.sample_rate, spec)
    assert mel_db.shape == (64, 100)
    assert mel_db.dtype == np.float32


def test_audio_curto_e_preenchido_ate_n_frames():
    spec = FeatureSpec(n_frames=200)
    mel_db = compute_melspec(_seno(440.0, 0.5, spec.sample_rate), spec.sample_rate, spec)
    assert mel_db.shape[1] == 200


def test_featurizacao_e_idempotente_byte_a_byte():
    """Não-determinismo aqui corromperia o cache de features silenciosamente."""
    spec = FeatureSpec()
    samples = _seno(440.0, 2.0, spec.sample_rate)
    a = compute_melspec(samples, spec.sample_rate, spec)
    b = compute_melspec(samples, spec.sample_rate, spec)
    assert a.tobytes() == b.tobytes()


def test_sample_rate_divergente_e_erro_ruidoso():
    spec = FeatureSpec()
    with pytest.raises(ValueError, match="sample rate"):
        compute_melspec(_seno(440.0, 1.0, 16000), 16000, spec)
