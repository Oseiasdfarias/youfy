# Pacote `youfy-audio`

O pacote `packages/audio` é responsável por processamento de sinal digital (DSP) e decodificação acústica.

---

## Princípio de Design: Funções Puras

- **Sem dependência de banco de dados:** Não importa SQLAlchemy, modelos ou conexões.
- **Sem chamadas de rede ou I/O externo:** Opera exclusivamente sobre arquivos de áudio locais ou buffers na memória.
- **Testabilidade determinística:** Testado via sinais analíticos sintéticos (seno de 440 Hz, ruído branco, silêncio), sem fixtures binárias de dados externos.

---

## Módulos

### 1. `youfy_audio.spec`
Define a classe de configuração `FeatureSpec` com:
- `fingerprint() -> str`: Hash SHA-256 estável de 16 caracteres.
- `effective_fmax -> float`: Frequência de corte Nyquist padrão ($sr / 2$).

### 2. `youfy_audio.melspec`
Computa o mel-espectrograma em decibéis:

```python
def compute_melspec(
    samples: np.ndarray, 
    sample_rate: int, 
    spec: FeatureSpec
) -> np.ndarray:
    ...
```

- **Referência fixa (`ref=1.0`):** Não utiliza normalização por pico local (`np.max`), preservando o loudness absoluto e a consistência entre clipes.
- **Dimensões garantidas:** Ajusta automaticamente para `(spec.n_mels, spec.n_frames)` com padding padronizado para áudios menores que a janela esperada.

### 3. `youfy_audio.decode`
Decodificação de áudio para matrizes NumPy e inspeção leve:

- `probe(path: str | Path) -> AudioProbe`: Realiza a leitura rápida apenas do cabeçalho do arquivo via `soundfile`, extraindo duração, taxa de amostragem e número de canais sem carregar amostras na memória.
- `decode(path: str | Path, target_sample_rate: int) -> np.ndarray`: Decodifica arquivos para `float32` mono, realizando reamostragem automática para a frequência de destino.

### 4. `youfy_audio.errors`
- `UnreadableAudio`: Exceção tipada lançada quando um arquivo está ausente, corrompido, truncado ou em formato não decodificável.

---

## Fluxo do Pipeline Acústico (DSP)

O diagrama abaixo ilustra o ciclo de vida da transformação desde o arquivo de áudio bruto no disco até a matriz tensorial pronta para o classificador:

```mermaid
flowchart TD
    subgraph RawAudio["1. Áudio Bruto em Disco"]
        File["Arquivo de Áudio (.mp3 / .wav / .flac)"]
    end

    subgraph Inspecao["2. Inspeção Rápida (Probe)"]
        Probe["soundfile.info()"]
        Meta["AudioProbe<br/>- duration_sec<br/>- sample_rate<br/>- channels"]
    end

    subgraph Decodificacao["3. Decodificação & Normalização"]
        Decode["soundfile.read()"]
        Mono["Conversão Estéreo → Mono (mean)"]
        Resample["Reamostragem (librosa.resample)"]
        Signal["Sinal PCM float32 [-1.0, +1.0]<br/>Taxa fixa: target_sample_rate"]
    end

    subgraph DSP["4. Extração de Features (Mel-Spectrogram)"]
        STFT["Short-Time Fourier Transform (STFT)<br/>n_fft = 2048, hop_length = 512"]
        Power["Magnitude ao Quadrado |STFT|²"]
        MelFilter["Banco de Filtros Mel (librosa.filters.mel)<br/>n_mels = 128, fmin=20Hz, fmax=Nyquist"]
        LogPower["Escala Logarítmica dB (ref=1.0)"]
        CropPad["Truncamento ou Zero-Padding Padronizado"]
    end

    subgraph Output["5. Tensor de Entrada para PyTorch / CNN"]
        Tensor["Tensor 2D NumPy float32<br/>Formato: (128 mel-bins, 1292 frames)<br/>Loudness absoluto preservado"]
    end

    File --> Probe --> Meta
    File --> Decode --> Mono --> Resample --> Signal
    Signal --> STFT --> Power --> MelFilter --> LogPower --> CropPad --> Tensor

    classDef raw fill:#161618,stroke:#3b82f6,stroke-width:1.5px,color:#f4f4f5;
    classDef proc fill:#18181b,stroke:#a855f7,stroke-width:1.5px,color:#f4f4f5;
    classDef dsp fill:#18181b,stroke:#10b981,stroke-width:1.5px,color:#f4f4f5;
    classDef out fill:#09090b,stroke:#06b6d4,stroke-width:2px,color:#38bdf8;
    class File raw;
    class Probe,Meta,Decode,Mono,Resample,Signal proc;
    class STFT,Power,MelFilter,LogPower,CropPad dsp;
    class Tensor out;
```
