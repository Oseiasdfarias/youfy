import numpy as np
import pytest
import soundfile as sf
from youfy_audio.decode import decode, probe
from youfy_audio.errors import UnreadableAudio


@pytest.fixture
def wav_valido(tmp_path):
    caminho = tmp_path / "ok.wav"
    sr = 44100
    t = np.linspace(0.0, 2.0, sr * 2, endpoint=False)
    sf.write(caminho, np.sin(2 * np.pi * 440.0 * t).astype(np.float32), sr)
    return caminho

@pytest.fixture
def wav_corrompido(tmp_path):
    caminho = tmp_path / "quebrado.wav"
    caminho.write_bytes(b"RIFF" + b"\x00lixo nao decodificavel" * 20)
    return caminho

def test_probe_le_metadados_sem_decodificar(wav_valido):
    info = probe(wav_valido)
    assert info.sample_rate == 44100
    assert info.channels == 1
    assert abs(info.duration_s - 2.0) < 0.01

def test_probe_em_arquivo_corrompido_levanta_unreadable(wav_corrompido):
    with pytest.raises(UnreadableAudio):
        probe(wav_corrompido)

def test_probe_em_arquivo_ausente_levanta_unreadable(tmp_path):
    with pytest.raises(UnreadableAudio):
        probe(tmp_path / "nao-existe.wav")

def test_decode_reamostra_para_o_alvo_e_retorna_mono_float32(wav_valido):
    samples = decode(wav_valido, target_sample_rate=22050)
    assert samples.dtype == np.float32
    assert samples.ndim == 1
    assert abs(len(samples) - 22050 * 2) < 100

def test_decode_em_arquivo_corrompido_levanta_unreadable(wav_corrompido):
    with pytest.raises(UnreadableAudio):
        decode(wav_corrompido, target_sample_rate=22050)
