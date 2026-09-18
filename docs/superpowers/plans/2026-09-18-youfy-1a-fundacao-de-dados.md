# Youfy 1A — Fundação de Dados: Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o pipeline `ingest → featurize → split` rodando sobre o `fma_small`, produzindo mel-espectrogramas versionados e splits com disjunção de artista garantida por teste.

**Architecture:** Monorepo `uv` com três pacotes de fronteira estrita. `audio` são funções puras sobre arrays (sem banco, sem rede). `catalog` é persistência e parsing de metadados (sem áudio). `pipelines` é a única camada que compõe os dois, expondo a CLI `youfy`. Estados intermediários são idempotentes e retomáveis; a invalidação de cache de features acontece por diretório derivado do fingerprint da `FeatureSpec`, nunca por deleção.

**Tech Stack:** Python 3.11+, uv, SQLAlchemy 2.0, Alembic, Postgres 16, librosa, soundfile, numpy, pandas, Typer, pytest, hypothesis, DVC, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-18-youfy-loop-fechado-minimo-design.md`

**Escopo:** Este é o plano 1A de 3 que implementam a Spec 1. O 1B cobre `ml` + `serving`; o 1C cobre `api` + `player`. Nada de MLflow, FastAPI, TUI ou event store aparece aqui.

## Global Constraints

- Python `>=3.11`. Gerenciador de dependências: `uv`, com `uv.lock` commitado.
- Postgres 16 local via `docker-compose`. Sem Supabase, sem serviço gerenciado.
- A CLI `youfy` (Typer) é a interface canônica. Alvos de `make` são atalhos finos sobre ela — **nunca lógica duplicada**.
- Direção de dependência estrita: `audio` e `catalog` **não importam um ao outro** e nenhum dos dois importa `pipelines`. Quem compõe é `pipelines`.
- `audio` é testável com sinal sintético, sem banco e sem rede. Se um teste de `audio` precisar de fixture binária, a fronteira vazou.
- Invariante de split: `artistas(train) ∩ artistas(test) == ∅` e o mesmo para `val`.
- Ingestão: se mais de **2%** das faixas do dump falharem, a CLI sai com código de erro.
- Logs estruturados em JSON.
- Trabalhe numa branch de feature. Não commite em `main`.
- Mensagens de commit sem qualquer identificação de IA.

---

### Task 1: Scaffold do workspace, Postgres e CI

**Files:**
- Create: `pyproject.toml`, `Makefile`, `docker-compose.yml`, `.gitignore`, `.env.example`
- Create: `packages/audio/pyproject.toml`, `packages/audio/src/youfy_audio/__init__.py`
- Create: `packages/catalog/pyproject.toml`, `packages/catalog/src/youfy_catalog/__init__.py`
- Create: `pipelines/pyproject.toml`, `pipelines/src/youfy_pipelines/__init__.py`
- Create: `.github/workflows/ci.yml`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: nada.
- Produces: o workspace `uv` com os três pacotes instaláveis em modo editável, e um Postgres alcançável em `postgresql://youfy:youfy@localhost:5433/youfy`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_workspace.py
import importlib

def test_os_tres_pacotes_sao_importaveis():
    for mod in ("youfy_audio", "youfy_catalog", "youfy_pipelines"):
        assert importlib.import_module(mod) is not None

def test_audio_nao_importa_catalog_nem_pipelines():
    """A fronteira do pacote `audio` é verificada, não confiada."""
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parents[1] / "packages/audio/src"
    fontes = "\n".join(p.read_text() for p in raiz.rglob("*.py"))
    assert "youfy_catalog" not in fontes
    assert "youfy_pipelines" not in fontes
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `uv run pytest tests/test_workspace.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_audio'`

- [ ] **Step 3: Criar o workspace uv**

```toml
# pyproject.toml (raiz)
[project]
name = "youfy"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "youfy-audio",
  "youfy-catalog",
  "youfy-pipelines",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "hypothesis>=6.100", "ruff>=0.6"]

[tool.uv.workspace]
members = ["packages/*", "pipelines"]

[tool.uv.sources]
youfy-audio = { workspace = true }
youfy-catalog = { workspace = true }
youfy-pipelines = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests", "packages/*/tests", "pipelines/tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```toml
# packages/audio/pyproject.toml
[project]
name = "youfy-audio"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["numpy>=1.26", "librosa>=0.10.2", "soundfile>=0.12.1"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```toml
# packages/catalog/pyproject.toml
[project]
name = "youfy-catalog"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "sqlalchemy>=2.0.30",
  "psycopg[binary]>=3.1",
  "alembic>=1.13",
  "pandas>=2.2",
  "pydantic-settings>=2.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

```toml
# pipelines/pyproject.toml
[project]
name = "youfy-pipelines"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["youfy-audio", "youfy-catalog", "typer>=0.12", "structlog>=24.1"]

[project.scripts]
youfy = "youfy_pipelines.cli:app"

[tool.uv.sources]
youfy-audio = { workspace = true }
youfy-catalog = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Crie os três `src/<pacote>/__init__.py` vazios.

- [ ] **Step 4: Criar o docker-compose e o .env.example**

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: youfy
      POSTGRES_PASSWORD: youfy
      POSTGRES_DB: youfy
    ports: ["5433:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U youfy"]
      interval: 3s
      retries: 10

volumes:
  pgdata:
```

Porta 5433 de propósito: evita colidir com um Postgres já rodando na 5432 da máquina.

```bash
# .env.example
YOUFY_DATABASE_URL=postgresql+psycopg://youfy:youfy@localhost:5433/youfy
YOUFY_DATA_DIR=./data
YOUFY_FMA_DUMP_DIR=./data/raw/fma
```

```gitignore
# .gitignore
.venv/
__pycache__/
*.pyc
.env
data/
!data/.gitkeep
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv sync --all-extras && uv run pytest tests/test_workspace.py -v`
Expected: PASS nos dois testes

- [ ] **Step 6: Criar o Makefile e o CI**

```makefile
# Makefile
.PHONY: setup up down lint test ingest featurize split

setup:
	uv sync --all-extras

up:
	docker compose up -d --wait

down:
	docker compose down

lint:
	uv run ruff check .

test:
	uv run pytest -v

ingest:
	uv run youfy pipeline ingest

featurize:
	uv run youfy pipeline featurize

split:
	uv run youfy pipeline split
```

```yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: youfy
          POSTGRES_PASSWORD: youfy
          POSTGRES_DB: youfy
        ports: ["5433:5432"]
        options: >-
          --health-cmd "pg_isready -U youfy" --health-interval 3s --health-retries 10
    env:
      YOUFY_DATABASE_URL: postgresql+psycopg://youfy:youfy@localhost:5433/youfy
      YOUFY_DATA_DIR: ./data
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: sudo apt-get update && sudo apt-get install -y libsndfile1 ffmpeg
      - run: uv sync --all-extras
      - run: uv run ruff check .
      - run: uv run pytest -v
```

- [ ] **Step 7: Verificar que o CI local passa e commitar**

Run: `make up && make lint && make test`
Expected: Postgres saudável, ruff limpo, testes passando

```bash
git add pyproject.toml uv.lock Makefile docker-compose.yml .gitignore .env.example \
        packages pipelines tests/test_workspace.py .github
git commit -m "chore: scaffold do workspace uv, postgres local e pipeline de ci"
```

---

### Task 2: `audio` — FeatureSpec e mel-espectrograma determinístico

**Files:**
- Create: `packages/audio/src/youfy_audio/spec.py`
- Create: `packages/audio/src/youfy_audio/melspec.py`
- Create: `packages/audio/tests/test_spec.py`
- Create: `packages/audio/tests/test_melspec.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `FeatureSpec(sample_rate:int=22050, n_fft:int=2048, hop_length:int=512, n_mels:int=128, n_frames:int=1292, fmin:float=0.0, fmax:float|None=None)` — dataclass congelada, com `.fingerprint() -> str` (16 hex) e `.effective_fmax -> float`.
  - `compute_melspec(samples: np.ndarray, sample_rate: int, spec: FeatureSpec) -> np.ndarray` — retorna `float32` de shape `(spec.n_mels, spec.n_frames)`, em dB.

- [ ] **Step 1: Escrever os testes que falham**

```python
# packages/audio/tests/test_spec.py
from youfy_audio.spec import FeatureSpec

def test_fingerprint_e_estavel_entre_instancias_iguais():
    assert FeatureSpec().fingerprint() == FeatureSpec().fingerprint()

def test_fingerprint_muda_quando_qualquer_campo_muda():
    base = FeatureSpec()
    assert FeatureSpec(n_mels=96).fingerprint() != base.fingerprint()
    assert FeatureSpec(hop_length=256).fingerprint() != base.fingerprint()

def test_fmax_efetivo_default_e_nyquist():
    assert FeatureSpec().effective_fmax == 22050 / 2
```

```python
# packages/audio/tests/test_melspec.py
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
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/audio/tests -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_audio.spec'`

- [ ] **Step 3: Implementar a FeatureSpec**

```python
# packages/audio/src/youfy_audio/spec.py
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """Configuração de featurização. Viaja junto com o artefato de modelo.

    n_frames default = 1292 ≈ 30s a 22050 Hz com hop de 512, que é a duração
    dos clipes do FMA.
    """

    sample_rate: int = 22050
    n_fft: int = 2048
    hop_length: int = 512
    n_mels: int = 128
    n_frames: int = 1292
    fmin: float = 0.0
    fmax: float | None = None
    top_db: float = 80.0

    @property
    def effective_fmax(self) -> float:
        return self.fmax if self.fmax is not None else self.sample_rate / 2

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()[:16]
```

- [ ] **Step 4: Implementar o melspec**

```python
# packages/audio/src/youfy_audio/melspec.py
from __future__ import annotations

import librosa
import numpy as np

from .spec import FeatureSpec

def compute_melspec(
    samples: np.ndarray, sample_rate: int, spec: FeatureSpec
) -> np.ndarray:
    """Mel-espectrograma em dB, com shape fixo `(spec.n_mels, spec.n_frames)`."""
    if sample_rate != spec.sample_rate:
        raise ValueError(
            f"sample rate divergente: recebido {sample_rate}, spec exige {spec.sample_rate}"
        )

    power = librosa.feature.melspectrogram(
        y=np.asarray(samples, dtype=np.float32),
        sr=sample_rate,
        n_fft=spec.n_fft,
        hop_length=spec.hop_length,
        n_mels=spec.n_mels,
        fmin=spec.fmin,
        fmax=spec.effective_fmax,
    )
    # ref=1.0 fixo, nunca np.max: normalizar por clipe destruiria a informação de
    # loudness absoluto e faria a mesma faixa gerar features diferentes conforme o
    # trecho, quebrando a comparabilidade entre treino e serving.
    db = librosa.power_to_db(power, ref=1.0, top_db=spec.top_db)
    return _ajustar_frames(db, spec.n_frames).astype(np.float32)

def _ajustar_frames(db: np.ndarray, n_frames: int) -> np.ndarray:
    atual = db.shape[1]
    if atual == n_frames:
        return db
    if atual > n_frames:
        return db[:, :n_frames]
    preenchimento = np.full((db.shape[0], n_frames - atual), db.min(), dtype=db.dtype)
    return np.concatenate([db, preenchimento], axis=1)
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/audio/tests -v`
Expected: PASS nos 8 testes

- [ ] **Step 6: Commitar**

```bash
git add packages/audio
git commit -m "feat(audio): FeatureSpec com fingerprint e melspec deterministico"
```

---

### Task 3: `audio` — decodificação e probe barato

**Files:**
- Create: `packages/audio/src/youfy_audio/decode.py`
- Create: `packages/audio/src/youfy_audio/errors.py`
- Create: `packages/audio/tests/test_decode.py`

**Interfaces:**
- Consumes: `FeatureSpec` da Task 2.
- Produces:
  - `UnreadableAudio(Exception)` — em `youfy_audio.errors`.
  - `AudioProbe(duration_s: float, sample_rate: int, channels: int)` — dataclass congelada.
  - `probe(path: str | Path) -> AudioProbe` — lê **só o cabeçalho**. Levanta `UnreadableAudio`.
  - `decode(path: str | Path, target_sample_rate: int) -> np.ndarray` — mono, `float32`, reamostrado. Levanta `UnreadableAudio`.

`probe` existe separado de `decode` porque a ingestão precisa validar 8.000 arquivos sem pagar o custo de decodificar todos.

- [ ] **Step 1: Escrever os testes que falham**

```python
# packages/audio/tests/test_decode.py
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
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/audio/tests/test_decode.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_audio.decode'`

- [ ] **Step 3: Implementar**

```python
# packages/audio/src/youfy_audio/errors.py
class UnreadableAudio(Exception):
    """Arquivo de áudio ausente, truncado ou em formato não decodificável."""
```

```python
# packages/audio/src/youfy_audio/decode.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from .errors import UnreadableAudio

@dataclass(frozen=True, slots=True)
class AudioProbe:
    duration_s: float
    sample_rate: int
    channels: int

def probe(path: str | Path) -> AudioProbe:
    """Lê apenas o cabeçalho. Barato o suficiente para rodar em todo o dump."""
    try:
        info = sf.info(str(path))
    except Exception as exc:  # soundfile levanta tipos variados por backend
        raise UnreadableAudio(f"nao foi possivel ler o cabecalho de {path}: {exc}") from exc
    return AudioProbe(
        duration_s=float(info.duration),
        sample_rate=int(info.samplerate),
        channels=int(info.channels),
    )

def decode(path: str | Path, target_sample_rate: int) -> np.ndarray:
    """Decodifica para mono float32 no sample rate alvo."""
    try:
        samples, _ = librosa.load(str(path), sr=target_sample_rate, mono=True)
    except Exception as exc:
        raise UnreadableAudio(f"nao foi possivel decodificar {path}: {exc}") from exc
    if samples.size == 0:
        raise UnreadableAudio(f"{path} decodificou para zero amostras")
    return np.asarray(samples, dtype=np.float32)
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/audio/tests -v`
Expected: PASS nos 13 testes (8 anteriores + 5 novos)

- [ ] **Step 5: Commitar**

```bash
git add packages/audio
git commit -m "feat(audio): probe barato e decode com erro tipado"
```

---

### Task 4: `catalog` — modelo de dados e migrations

**Files:**
- Create: `packages/catalog/src/youfy_catalog/settings.py`
- Create: `packages/catalog/src/youfy_catalog/db.py`
- Create: `packages/catalog/src/youfy_catalog/models.py`
- Create: `packages/catalog/alembic.ini`, `packages/catalog/migrations/env.py`, e a revisao gerada em `packages/catalog/migrations/versions/` (o nome sai do autogenerate)
- Create: `conftest.py` (raiz do repo), `packages/catalog/tests/test_models.py`

**Interfaces:**
- Consumes: nada de outros pacotes.
- Produces:
  - `Settings` (pydantic-settings) com `database_url: str`, `data_dir: Path`, prefixo de env `YOUFY_`.
  - `get_engine()`, `session_scope()` — context manager que comita ou faz rollback.
  - Modelos `Artist`, `Genre`, `Track`, `TrackGenre`, `IngestFailure`, `Feature` (SQLAlchemy 2.0 `DeclarativeBase`).

A tabela `features` guarda `spec_fingerprint`, o que permite conviverem features de configs diferentes sem apagar nada.

- [ ] **Step 1: Escrever os testes que falham**

```python
# conftest.py  (raiz do repositorio: estas fixtures precisam valer para todos os pacotes)
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from youfy_catalog.models import Base
from youfy_catalog.settings import Settings

@pytest.fixture
def engine():
    eng = create_engine(Settings().database_url, future=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)

@pytest.fixture
def session(engine):
    with sessionmaker(bind=engine, future=True)() as s:
        yield s
```

```python
# packages/catalog/tests/test_models.py
import pytest
from sqlalchemy.exc import IntegrityError
from youfy_catalog.models import Artist, Feature, Genre, IngestFailure, Track, TrackGenre

def _artista(session, ident="fma:artist:1"):
    a = Artist(id=ident, name="Banda Teste", source="fma")
    session.add(a)
    session.flush()
    return a

def test_track_exige_artista_existente(session):
    session.add(Track(id="fma:track:1", artist_id="fma:artist:inexistente",
                      title="t", duration_ms=1000, audio_path="/x.wav", source="fma"))
    with pytest.raises(IntegrityError):
        session.flush()

def test_track_persiste_com_genero_top(session):
    _artista(session)
    session.add(Track(id="fma:track:1", artist_id="fma:artist:1", title="t",
                      duration_ms=30000, audio_path="/x.wav", top_genre="Rock", source="fma"))
    session.flush()
    assert session.get(Track, "fma:track:1").top_genre == "Rock"

def test_track_genre_e_unico_por_par(session):
    _artista(session)
    session.add_all([
        Track(id="fma:track:1", artist_id="fma:artist:1", title="t",
              duration_ms=1, audio_path="/x.wav", source="fma"),
        Genre(id=12, name="Rock", parent_id=None),
    ])
    session.flush()
    session.add(TrackGenre(track_id="fma:track:1", genre_id=12))
    session.flush()
    session.add(TrackGenre(track_id="fma:track:1", genre_id=12))
    with pytest.raises(IntegrityError):
        session.flush()

def test_ingest_failure_registra_motivo(session):
    session.add(IngestFailure(source_ref="fma:track:99", reason="unreadable_audio",
                              detail="cabecalho invalido"))
    session.flush()
    assert session.query(IngestFailure).count() == 1

def test_feature_e_unica_por_track_e_fingerprint(session):
    _artista(session)
    session.add(Track(id="fma:track:1", artist_id="fma:artist:1", title="t",
                      duration_ms=1, audio_path="/x.wav", source="fma"))
    session.flush()
    session.add(Feature(track_id="fma:track:1", spec_fingerprint="abc123",
                        path="/f.npy", status="ok"))
    session.flush()
    session.add(Feature(track_id="fma:track:1", spec_fingerprint="abc123",
                        path="/outro.npy", status="ok"))
    with pytest.raises(IntegrityError):
        session.flush()
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `make up && uv run pytest packages/catalog/tests -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_catalog.models'`

- [ ] **Step 3: Implementar settings e sessão**

```python
# packages/catalog/src/youfy_catalog/settings.py
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YOUFY_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://youfy:youfy@localhost:5433/youfy"
    data_dir: Path = Path("./data")
    fma_dump_dir: Path = Path("./data/raw/fma")
```

```python
# packages/catalog/src/youfy_catalog/db.py
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .settings import Settings

@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(Settings().database_url, future=True, pool_pre_ping=True)

@contextmanager
def session_scope() -> Iterator[Session]:
    factory = sessionmaker(bind=get_engine(), future=True)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

- [ ] **Step 4: Implementar os modelos**

```python
# packages/catalog/src/youfy_catalog/models.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def _agora() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Artist(Base):
    __tablename__ = "artists"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)

class Genre(Base):
    __tablename__ = "genres"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    artist_id: Mapped[str] = mapped_column(ForeignKey("artists.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    audio_path: Mapped[str] = mapped_column(Text, nullable=False)
    top_genre: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class TrackGenre(Base):
    __tablename__ = "track_genres"
    __table_args__ = (UniqueConstraint("track_id", "genre_id", name="uq_track_genre"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), nullable=False)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"), nullable=False)

class IngestFailure(Base):
    __tablename__ = "ingest_failures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

class Feature(Base):
    """Uma linha por (faixa, fingerprint de FeatureSpec).

    Guardar o fingerprint permite que features de configs diferentes coexistam
    sem que uma invalide a outra por deleção.
    """

    __tablename__ = "features"
    __table_args__ = (
        UniqueConstraint("track_id", "spec_fingerprint", name="uq_feature_track_spec"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), nullable=False, index=True)
    spec_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # ok | failed
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/catalog/tests -v`
Expected: PASS nos 5 testes

- [ ] **Step 6: Gerar a migration inicial e verificar que ela reproduz o schema**

```bash
cd packages/catalog
uv run alembic init -t generic migrations   # se ainda não existir
```

Ajuste `migrations/env.py` para usar os metadados e a URL das Settings:

```python
# packages/catalog/migrations/env.py  (trecho relevante)
from alembic import context
from sqlalchemy import engine_from_config, pool

from youfy_catalog.models import Base
from youfy_catalog.settings import Settings

config = context.config
config.set_main_option("sqlalchemy.url", Settings().database_url)
target_metadata = Base.metadata

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

```bash
uv run alembic revision --autogenerate -m "inicial"
uv run alembic upgrade head
uv run alembic check   # deve reportar que não há diferença pendente
```

Expected: `alembic check` sem diferenças — o schema dos modelos e o da migration batem

- [ ] **Step 7: Commitar**

```bash
git add packages/catalog
git commit -m "feat(catalog): modelo de dados do acervo e migration inicial"
```

---

### Task 5: `catalog` — leitura do dump FMA e escrita do acervo

**Files:**
- Create: `packages/catalog/src/youfy_catalog/fma.py`
- Create: `packages/catalog/src/youfy_catalog/repository.py`
- Create: `packages/catalog/src/youfy_catalog/testing.py`
- Create: `packages/catalog/tests/test_fma.py`, `packages/catalog/tests/test_repository.py`

**Interfaces:**
- Consumes: modelos e `session_scope` da Task 4.
- Produces:
  - `FmaTrackRow(track_id:int, title:str, genre_top:str|None, duration_s:float, artist_id:int, artist_name:str, subset:str)` — dataclass congelada.
  - `read_tracks_csv(path: Path, subset: str | None = None) -> list[FmaTrackRow]`
  - `audio_path_for(track_id: int, audio_root: Path, ext: str = ".mp3") -> Path`
  - `upsert_artist(session, *, id, name, source) -> None`
  - `upsert_track(session, *, id, artist_id, title, duration_ms, audio_path, top_genre, source) -> None`
  - `record_failure(session, *, source_ref, reason, detail) -> None`
  - `FixtureTrack(track_id:int, artist_id:int, artist_name:str, genre_top:str|None, corrompido:bool=False)`
  - `build_fma_fixture(root: Path, faixas: list[FixtureTrack], sr: int = 22050) -> Path`

`read_tracks_csv` precisa lidar com o cabeçalho de dois níveis do `tracks.csv` do FMA — é o detalhe que mais derruba quem encosta nesse dataset pela primeira vez.

- [ ] **Step 1: Escrever o construtor de fixture e os testes que falham**

```python
# packages/catalog/src/youfy_catalog/testing.py
"""Construtor de acervo sintetico com a forma do FMA, incluindo o cabecalho de 2 niveis.

Vive em `src/`, nao em `tests/`, porque e importado por testes de outros
pacotes -- `packages/catalog/tests/` nao e um pacote importavel.

Usa .wav em vez de .mp3 porque o `soundfile` escreve wav de forma confiável em
qualquer plataforma; a extensão é parâmetro do leitor, então o formato do teste
não vaza para produção.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

@dataclass(frozen=True)
class FixtureTrack:
    track_id: int
    artist_id: int
    artist_name: str
    genre_top: str | None
    corrompido: bool = False

def build_fma_fixture(root: Path, faixas: list[FixtureTrack], sr: int = 22050) -> Path:
    meta_dir = root / "fma_metadata"
    audio_dir = root / "fma_small"
    meta_dir.mkdir(parents=True, exist_ok=True)

    colunas = pd.MultiIndex.from_tuples([
        ("set", "subset"), ("track", "title"), ("track", "genre_top"),
        ("track", "duration"), ("artist", "id"), ("artist", "name"),
    ])
    linhas = []
    for f in faixas:
        pasta = audio_dir / f"{f.track_id // 1000:03d}"
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{f.track_id:06d}.wav"
        if f.corrompido:
            destino.write_bytes(b"RIFF" + b"\x00lixo" * 40)
        else:
            t = np.linspace(0.0, 1.0, sr, endpoint=False)
            sf.write(destino, np.sin(2 * np.pi * 440.0 * t).astype(np.float32), sr)
        genero = "" if f.genre_top is None else f.genre_top
        linhas.append(["small", f"Faixa {f.track_id}", genero, 1.0,
                       f.artist_id, f.artist_name])

    df = pd.DataFrame(linhas, columns=colunas, index=[f.track_id for f in faixas])
    df.index.name = "track_id"
    df.to_csv(meta_dir / "tracks.csv")
    return root
```

```python
# packages/catalog/tests/test_fma.py
from pathlib import Path

from youfy_catalog.fma import audio_path_for, read_tracks_csv

from youfy_catalog.testing import FixtureTrack, build_fma_fixture

def test_le_o_cabecalho_de_dois_niveis_do_tracks_csv(tmp_path):
    build_fma_fixture(tmp_path, [
        FixtureTrack(2, 10, "Artista A", "Rock"),
        FixtureTrack(1005, 11, "Artista B", "Jazz"),
    ])
    linhas = read_tracks_csv(tmp_path / "fma_metadata" / "tracks.csv")
    assert {l.track_id for l in linhas} == {2, 1005}
    assert {l.genre_top for l in linhas} == {"Rock", "Jazz"}
    assert {l.artist_name for l in linhas} == {"Artista A", "Artista B"}

def test_filtra_por_subset(tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", "Rock")])
    assert len(read_tracks_csv(tmp_path / "fma_metadata" / "tracks.csv", subset="small")) == 1
    assert read_tracks_csv(tmp_path / "fma_metadata" / "tracks.csv", subset="large") == []

def test_caminho_de_audio_usa_o_particionamento_por_milhar():
    raiz = Path("/dados/fma_small")
    assert audio_path_for(2, raiz, ext=".mp3") == raiz / "000" / "000002.mp3"
    assert audio_path_for(1005, raiz, ext=".wav") == raiz / "001" / "001005.wav"
```

```python
# packages/catalog/tests/test_repository.py
from youfy_catalog.models import Artist, IngestFailure, Track
from youfy_catalog.repository import record_failure, upsert_artist, upsert_track

def test_upsert_track_e_idempotente(session):
    upsert_artist(session, id="fma:artist:1", name="A", source="fma")
    for titulo in ("primeiro", "segundo"):
        upsert_track(session, id="fma:track:1", artist_id="fma:artist:1", title=titulo,
                     duration_ms=1000, audio_path="/x.wav", top_genre="Rock", source="fma")
    session.flush()
    assert session.query(Track).count() == 1
    assert session.get(Track, "fma:track:1").title == "segundo"

def test_upsert_artist_e_idempotente(session):
    for nome in ("A", "A renomeado"):
        upsert_artist(session, id="fma:artist:1", name=nome, source="fma")
    session.flush()
    assert session.query(Artist).count() == 1
    assert session.get(Artist, "fma:artist:1").name == "A renomeado"

def test_record_failure_persiste(session):
    record_failure(session, source_ref="fma:track:9", reason="unreadable_audio", detail="ruim")
    session.flush()
    assert session.query(IngestFailure).one().reason == "unreadable_audio"
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/catalog/tests/test_fma.py packages/catalog/tests/test_repository.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_catalog.fma'`

- [ ] **Step 3: Implementar o leitor do FMA**

```python
# packages/catalog/src/youfy_catalog/fma.py
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

@dataclass(frozen=True, slots=True)
class FmaTrackRow:
    track_id: int
    title: str
    genre_top: str | None
    duration_s: float
    artist_id: int
    artist_name: str
    subset: str

def read_tracks_csv(path: Path, subset: str | None = None) -> list[FmaTrackRow]:
    """Lê o `tracks.csv` do FMA, que traz cabeçalho de dois níveis."""
    raw = pd.read_csv(path, index_col=0, header=[0, 1], low_memory=False)
    linhas: list[FmaTrackRow] = []
    for track_id, r in raw.iterrows():
        subset_da_linha = str(r[("set", "subset")])
        if subset is not None and subset_da_linha != subset:
            continue
        genero = r[("track", "genre_top")]
        linhas.append(
            FmaTrackRow(
                track_id=int(track_id),
                title=str(r[("track", "title")]),
                genre_top=None if _vazio(genero) else str(genero),
                duration_s=float(r[("track", "duration")]),
                artist_id=int(r[("artist", "id")]),
                artist_name=str(r[("artist", "name")]),
                subset=subset_da_linha,
            )
        )
    return linhas

def audio_path_for(track_id: int, audio_root: Path, ext: str = ".mp3") -> Path:
    """O FMA particiona os arquivos em pastas de mil: 001005 vive em `001/`."""
    return audio_root / f"{track_id // 1000:03d}" / f"{track_id:06d}{ext}"

def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor)) or valor == ""
```

- [ ] **Step 4: Implementar o repositório**

```python
# packages/catalog/src/youfy_catalog/repository.py
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import Artist, IngestFailure, Track

def upsert_artist(session: Session, *, id: str, name: str, source: str) -> None:
    stmt = insert(Artist).values(id=id, name=name, source=source)
    session.execute(
        stmt.on_conflict_do_update(index_elements=["id"], set_={"name": name, "source": source})
    )

def upsert_track(
    session: Session,
    *,
    id: str,
    artist_id: str,
    title: str,
    duration_ms: int,
    audio_path: str,
    source: str,
    top_genre: str | None = None,
) -> None:
    valores = dict(
        id=id, artist_id=artist_id, title=title, duration_ms=duration_ms,
        audio_path=audio_path, top_genre=top_genre, source=source,
    )
    stmt = insert(Track).values(**valores)
    atualizaveis = {k: v for k, v in valores.items() if k != "id"}
    session.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=atualizaveis))

def record_failure(session: Session, *, source_ref: str, reason: str, detail: str | None) -> None:
    session.add(IngestFailure(source_ref=source_ref, reason=reason, detail=detail))
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/catalog/tests -v`
Expected: PASS nos 11 testes

- [ ] **Step 6: Commitar**

```bash
git add packages/catalog
git commit -m "feat(catalog): leitor do dump fma e repositorio idempotente"
```

---

### Task 6: `pipelines` — CLI, logging estruturado e o estágio `ingest`

**Files:**
- Create: `pipelines/src/youfy_pipelines/logging.py`
- Create: `pipelines/src/youfy_pipelines/ingest.py`
- Create: `pipelines/src/youfy_pipelines/cli.py`
- Create: `pipelines/tests/test_ingest.py`

**Interfaces:**
- Consumes: `probe`/`UnreadableAudio` (Task 3); `read_tracks_csv`/`audio_path_for` (Task 5); `upsert_artist`/`upsert_track`/`record_failure` (Task 5); `session_scope` (Task 4).
- Produces:
  - `IngestReport(total:int, ingested:int, failed:int)` com `.failure_rate -> float`.
  - `run_ingest(session, *, dump_dir: Path, subset: str = "small", audio_ext: str = ".mp3") -> IngestReport`
  - `configure_logging() -> None`
  - CLI: `youfy pipeline ingest [--dump-dir] [--subset] [--audio-ext] [--max-failure-rate]`

**Nota de fronteira:** é aqui que `audio` e `catalog` se encontram pela primeira vez. `catalog` continua sem saber o que é um mel-espectrograma e `audio` continua sem saber o que é um banco. A composição mora em `pipelines`, e só nele.

- [ ] **Step 1: Escrever os testes que falham**

```python
# pipelines/tests/test_ingest.py
import pytest
from youfy_catalog.models import IngestFailure, Track
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_pipelines.ingest import run_ingest


def test_ingere_faixas_validas_e_quarentena_as_corrompidas(session, tmp_path):
    build_fma_fixture(tmp_path, [
        FixtureTrack(2, 10, "Artista A", "Rock"),
        FixtureTrack(3, 10, "Artista A", "Rock"),
        FixtureTrack(1005, 11, "Artista B", "Jazz", corrompido=True),
    ])
    relatorio = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()

    assert relatorio.total == 3
    assert relatorio.ingested == 2
    assert relatorio.failed == 1
    assert session.query(Track).count() == 2
    assert session.query(IngestFailure).one().reason == "unreadable_audio"

def test_arquivo_ausente_vira_quarentena_e_nao_excecao(session, tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", "Rock")])
    (tmp_path / "fma_small" / "000" / "000002.wav").unlink()
    relatorio = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert relatorio.ingested == 0
    assert session.query(IngestFailure).one().reason == "unreadable_audio"

def test_faixa_sem_genero_top_vira_quarentena(session, tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", genre_top=None)])
    relatorio = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert relatorio.ingested == 0
    assert session.query(IngestFailure).one().reason == "missing_genre"

def test_reexecucao_e_idempotente(session, tmp_path):
    build_fma_fixture(tmp_path, [FixtureTrack(2, 10, "A", "Rock")])
    for _ in range(2):
        run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert session.query(Track).count() == 1

def test_taxa_de_falha_e_calculada():
    from youfy_pipelines.ingest import IngestReport
    assert IngestReport(total=100, ingested=97, failed=3).failure_rate == pytest.approx(0.03)
    assert IngestReport(total=0, ingested=0, failed=0).failure_rate == 0.0
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest pipelines/tests/test_ingest.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_pipelines.ingest'`

- [ ] **Step 3: Implementar o logging estruturado**

```python
# pipelines/src/youfy_pipelines/logging.py
import logging

import structlog

def configure_logging(level: int = logging.INFO) -> None:
    """Logs em JSON — a spec exige, e é o que torna o pipeline analisável depois."""
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 4: Implementar o estágio de ingestão**

```python
# pipelines/src/youfy_pipelines/ingest.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog
from sqlalchemy.orm import Session
from youfy_audio.decode import probe
from youfy_audio.errors import UnreadableAudio
from youfy_catalog.fma import audio_path_for, read_tracks_csv
from youfy_catalog.repository import record_failure, upsert_artist, upsert_track

log = structlog.get_logger()

@dataclass(frozen=True, slots=True)
class IngestReport:
    total: int
    ingested: int
    failed: int

    @property
    def failure_rate(self) -> float:
        return self.failed / self.total if self.total else 0.0

def run_ingest(
    session: Session,
    *,
    dump_dir: Path,
    subset: str = "small",
    audio_ext: str = ".mp3",
) -> IngestReport:
    """Falha de dado vira quarentena; a execução nunca para por causa de uma faixa."""
    linhas = read_tracks_csv(dump_dir / "fma_metadata" / "tracks.csv", subset=subset)
    audio_root = dump_dir / f"fma_{subset}"
    ingeridas = falhas = 0

    for linha in linhas:
        ref = f"fma:track:{linha.track_id}"
        if linha.genre_top is None:
            record_failure(session, source_ref=ref, reason="missing_genre", detail=None)
            falhas += 1
            continue

        caminho = audio_path_for(linha.track_id, audio_root, ext=audio_ext)
        try:
            info = probe(caminho)
        except UnreadableAudio as exc:
            record_failure(session, source_ref=ref, reason="unreadable_audio", detail=str(exc))
            falhas += 1
            continue

        artist_id = f"fma:artist:{linha.artist_id}"
        upsert_artist(session, id=artist_id, name=linha.artist_name, source="fma")
        upsert_track(
            session,
            id=ref,
            artist_id=artist_id,
            title=linha.title,
            duration_ms=int(info.duration_s * 1000),
            audio_path=str(caminho),
            top_genre=linha.genre_top,
            source="fma",
        )
        ingeridas += 1

    relatorio = IngestReport(total=len(linhas), ingested=ingeridas, failed=falhas)
    log.info("ingest.concluido", total=relatorio.total, ingeridas=ingeridas,
             falhas=falhas, taxa_de_falha=round(relatorio.failure_rate, 4))
    return relatorio
```

- [ ] **Step 5: Implementar a CLI**

```python
# pipelines/src/youfy_pipelines/cli.py
from __future__ import annotations

from pathlib import Path

import typer
from youfy_catalog.db import session_scope
from youfy_catalog.settings import Settings

from .ingest import run_ingest
from .logging import configure_logging

app = typer.Typer(help="Youfy — pipelines de dados e treino.")
pipeline = typer.Typer(help="Estágios do pipeline offline.")
app.add_typer(pipeline, name="pipeline")

@pipeline.command("ingest")
def ingest_cmd(
    dump_dir: Path = typer.Option(None, help="Raiz do dump do FMA."),
    subset: str = typer.Option("small"),
    audio_ext: str = typer.Option(".mp3"),
    max_failure_rate: float = typer.Option(0.02, help="Acima disso, sai com erro."),
) -> None:
    configure_logging()
    raiz = dump_dir or Settings().fma_dump_dir
    with session_scope() as session:
        relatorio = run_ingest(session, dump_dir=raiz, subset=subset, audio_ext=audio_ext)

    typer.echo(
        f"total={relatorio.total} ingeridas={relatorio.ingested} "
        f"falhas={relatorio.failed} taxa={relatorio.failure_rate:.4f}"
    )
    if relatorio.failure_rate > max_failure_rate:
        typer.echo(
            f"ERRO: taxa de falha {relatorio.failure_rate:.4f} acima do limite "
            f"{max_failure_rate:.4f}",
            err=True,
        )
        raise typer.Exit(code=1)
```

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `uv run pytest pipelines/tests/test_ingest.py -v && uv run youfy pipeline --help`
Expected: PASS nos 5 testes; o help lista o comando `ingest`

- [ ] **Step 7: Commitar**

```bash
git add pipelines
git commit -m "feat(pipelines): cli youfy, logging estruturado e estagio de ingestao"
```

---

### Task 7: `pipelines` — featurize idempotente e retomável

**Files:**
- Create: `pipelines/src/youfy_pipelines/featurize.py`
- Modify: `pipelines/src/youfy_pipelines/cli.py` (adicionar o comando `featurize`)
- Create: `pipelines/tests/test_featurize.py`

**Interfaces:**
- Consumes: `FeatureSpec`/`compute_melspec` (Task 2); `decode`/`UnreadableAudio` (Task 3); modelos `Track`/`Feature` (Task 4); `session_scope` (Task 4).
- Produces:
  - `FeaturizeReport(total:int, computed:int, skipped:int, failed:int)`
  - `features_dir(data_dir: Path, spec: FeatureSpec) -> Path` → `data_dir/features/melspec/<fingerprint>/`
  - `write_manifest(dir: Path, spec: FeatureSpec) -> None`
  - `run_featurize(session, *, data_dir: Path, spec: FeatureSpec) -> FeaturizeReport`
  - CLI: `youfy pipeline featurize [--data-dir] [--n-mels] [--hop-length]`

A invalidação de cache acontece por **diretório derivado do fingerprint**. Mudar a config não apaga nada: cria um diretório novo ao lado. É o que torna o estágio seguro para interromper e reexecutar à vontade.

- [ ] **Step 1: Escrever os testes que falham**

```python
# pipelines/tests/test_featurize.py
import json

import numpy as np
from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Feature
from youfy_catalog.repository import upsert_artist, upsert_track
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_pipelines.featurize import features_dir, run_featurize


def _acervo(session, tmp_path, ids=(2, 3)):
    faixas = [FixtureTrack(i, 10, "A", "Rock") for i in ids]
    build_fma_fixture(tmp_path, faixas)
    upsert_artist(session, id="fma:artist:10", name="A", source="fma")
    for i in ids:
        caminho = tmp_path / "fma_small" / f"{i // 1000:03d}" / f"{i:06d}.wav"
        upsert_track(session, id=f"fma:track:{i}", artist_id="fma:artist:10",
                     title=f"t{i}", duration_ms=1000, audio_path=str(caminho),
                     top_genre="Rock", source="fma")
    session.flush()

def test_gera_um_npy_por_faixa_com_o_shape_da_spec(session, tmp_path):
    _acervo(session, tmp_path)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    relatorio = run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    session.flush()

    assert relatorio.computed == 2
    destino = features_dir(tmp_path / "data", spec)
    arr = np.load(destino / "fma_track_2.npy")
    assert arr.shape == (32, 40)
    assert arr.dtype == np.float32
    assert session.query(Feature).filter_by(status="ok").count() == 2

def test_reexecucao_pula_o_que_ja_existe(session, tmp_path):
    _acervo(session, tmp_path)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    session.flush()
    segunda = run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    assert segunda.computed == 0
    assert segunda.skipped == 2

def test_config_diferente_gera_diretorio_novo_sem_apagar_o_anterior(session, tmp_path):
    _acervo(session, tmp_path)
    antiga = FeatureSpec(n_mels=32, n_frames=40)
    nova = FeatureSpec(n_mels=16, n_frames=40)
    run_featurize(session, data_dir=tmp_path / "data", spec=antiga)
    run_featurize(session, data_dir=tmp_path / "data", spec=nova)
    session.flush()
    assert (features_dir(tmp_path / "data", antiga) / "fma_track_2.npy").exists()
    assert (features_dir(tmp_path / "data", nova) / "fma_track_2.npy").exists()

def test_audio_ilegivel_vira_feature_failed_sem_derrubar(session, tmp_path):
    _acervo(session, tmp_path, ids=(2, 3))
    (tmp_path / "fma_small" / "000" / "000003.wav").write_bytes(b"RIFF" + b"\x00lixo" * 40)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    relatorio = run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    session.flush()
    assert relatorio.computed == 1
    assert relatorio.failed == 1
    assert session.query(Feature).filter_by(status="failed").count() == 1

def test_manifest_registra_a_spec(session, tmp_path):
    _acervo(session, tmp_path)
    spec = FeatureSpec(n_mels=32, n_frames=40)
    run_featurize(session, data_dir=tmp_path / "data", spec=spec)
    manifesto = json.loads((features_dir(tmp_path / "data", spec) / "_manifest.json").read_text())
    assert manifesto["fingerprint"] == spec.fingerprint()
    assert manifesto["spec"]["n_mels"] == 32
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest pipelines/tests/test_featurize.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_pipelines.featurize'`

- [ ] **Step 3: Implementar**

```python
# pipelines/src/youfy_pipelines/featurize.py
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from youfy_audio.decode import decode
from youfy_audio.errors import UnreadableAudio
from youfy_audio.melspec import compute_melspec
from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Feature, Track

log = structlog.get_logger()

@dataclass(frozen=True, slots=True)
class FeaturizeReport:
    total: int
    computed: int
    skipped: int
    failed: int

def features_dir(data_dir: Path, spec: FeatureSpec) -> Path:
    return data_dir / "features" / "melspec" / spec.fingerprint()

def write_manifest(destino: Path, spec: FeatureSpec) -> None:
    (destino / "_manifest.json").write_text(
        json.dumps({"fingerprint": spec.fingerprint(), "spec": asdict(spec)}, indent=2)
    )

def _nome_arquivo(track_id: str) -> str:
    return track_id.replace(":", "_") + ".npy"

def run_featurize(session: Session, *, data_dir: Path, spec: FeatureSpec) -> FeaturizeReport:
    destino = features_dir(data_dir, spec)
    destino.mkdir(parents=True, exist_ok=True)
    write_manifest(destino, spec)

    faixas = session.execute(select(Track)).scalars().all()
    computadas = puladas = falhas = 0

    for faixa in faixas:
        arquivo = destino / _nome_arquivo(faixa.id)
        # A presença do arquivo é o sinal de retomada: sem estado extra para
        # dessincronizar, e seguro contra interrupção no meio de 8 mil faixas.
        if arquivo.exists():
            puladas += 1
            continue

        try:
            samples = decode(faixa.audio_path, target_sample_rate=spec.sample_rate)
            mel = compute_melspec(samples, spec.sample_rate, spec)
        except UnreadableAudio as exc:
            _registrar_feature(session, faixa.id, spec, path=None,
                               status="failed", detail=str(exc))
            falhas += 1
            continue

        np.save(arquivo, mel)
        _registrar_feature(session, faixa.id, spec, path=str(arquivo),
                           status="ok", detail=None)
        computadas += 1

    relatorio = FeaturizeReport(len(faixas), computadas, puladas, falhas)
    log.info("featurize.concluido", fingerprint=spec.fingerprint(), total=relatorio.total,
             computadas=computadas, puladas=puladas, falhas=falhas)
    return relatorio

def _registrar_feature(
    session: Session, track_id: str, spec: FeatureSpec, *,
    path: str | None, status: str, detail: str | None,
) -> None:
    stmt = insert(Feature).values(
        track_id=track_id, spec_fingerprint=spec.fingerprint(),
        path=path, status=status, detail=detail,
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["track_id", "spec_fingerprint"],
            set_={"path": path, "status": status, "detail": detail},
        )
    )
```

- [ ] **Step 4: Adicionar o comando à CLI**

```python
# pipelines/src/youfy_pipelines/cli.py  — acrescentar

from youfy_audio.spec import FeatureSpec

from .featurize import run_featurize

@pipeline.command("featurize")
def featurize_cmd(
    data_dir: Path = typer.Option(None),
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
) -> None:
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    with session_scope() as session:
        relatorio = run_featurize(session, data_dir=raiz, spec=spec)
    typer.echo(
        f"fingerprint={spec.fingerprint()} total={relatorio.total} "
        f"computadas={relatorio.computed} puladas={relatorio.skipped} "
        f"falhas={relatorio.failed}"
    )
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv run pytest pipelines/tests -v`
Expected: PASS nos 10 testes (5 de ingest + 5 de featurize)

- [ ] **Step 6: Commitar**

```bash
git add pipelines
git commit -m "feat(pipelines): featurize idempotente com cache por fingerprint"
```

---

### Task 8: `pipelines` — split agrupado por artista

**Files:**
- Create: `pipelines/src/youfy_pipelines/split.py`
- Modify: `pipelines/src/youfy_pipelines/cli.py` (adicionar o comando `split`)
- Create: `pipelines/tests/test_split.py`

**Interfaces:**
- Consumes: modelos `Track`/`Feature` (Task 4); `FeatureSpec` (Task 2).
- Produces:
  - `TrackRef(track_id:str, artist_id:str, genre:str)` — dataclass congelada.
  - `Splits(train:list[str], val:list[str], test:list[str])` com `.as_dict() -> dict[str, list[str]]`
  - `make_splits(refs: list[TrackRef], *, seed: int, ratios: tuple[float,float,float]=(0.7,0.15,0.15)) -> Splits`
  - `run_split(session, *, data_dir: Path, spec: FeatureSpec, seed: int, ratios) -> Splits` — lê só faixas com `Feature.status == "ok"`; escreve `data_dir/splits/<fingerprint>/{train,val,test}.json`.
  - CLI: `youfy pipeline split [--data-dir] [--seed] [--n-mels] [--hop-length]`

**O invariante:** nenhum artista aparece em mais de um split. Se o mesmo artista estiver em treino e teste, o modelo aprende timbre de produção em vez de gênero, e a acurácia infla silenciosamente. O FMA é especialmente sujeito a isso por ter muitas faixas por artista.

**Algoritmo:** agrupar faixas por `(gênero, artista)`; dentro de cada gênero, ordenar os artistas por número de faixas em ordem decrescente, com desempate pelo embaralhamento semeado; atribuir cada artista ao split cujo déficit em relação à cota-alvo daquele gênero for maior. Guloso, determinístico e garante disjunção por construção.

- [ ] **Step 1: Escrever os testes que falham**

```python
# pipelines/tests/test_split.py
import json

from hypothesis import given, settings
from hypothesis import strategies as st
from youfy_pipelines.split import TrackRef, make_splits

def _refs(por_artista: dict[str, tuple[str, int]]) -> list[TrackRef]:
    saida = []
    for artista, (genero, n) in por_artista.items():
        saida += [TrackRef(f"t:{artista}:{i}", artista, genero) for i in range(n)]
    return saida

def test_nenhum_artista_cruza_splits():
    refs = _refs({f"a{i}": ("Rock" if i % 2 else "Jazz", 3) for i in range(40)})
    s = make_splits(refs, seed=7)
    por_split = {
        nome: {r.artist_id for r in refs if r.track_id in set(ids)}
        for nome, ids in s.as_dict().items()
    }
    assert por_split["train"] & por_split["test"] == set()
    assert por_split["train"] & por_split["val"] == set()
    assert por_split["val"] & por_split["test"] == set()

def test_toda_faixa_e_atribuida_exatamente_uma_vez():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(30)})
    s = make_splits(refs, seed=1)
    todos = s.train + s.val + s.test
    assert len(todos) == len(refs)
    assert set(todos) == {r.track_id for r in refs}

def test_e_deterministico_para_a_mesma_seed():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(30)})
    assert make_splits(refs, seed=42).as_dict() == make_splits(refs, seed=42).as_dict()

def test_seeds_diferentes_produzem_particoes_diferentes():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(60)})
    assert make_splits(refs, seed=1).as_dict() != make_splits(refs, seed=2).as_dict()

def test_proporcoes_ficam_perto_do_alvo_com_artistas_suficientes():
    refs = _refs({f"a{i}": ("Rock", 2) for i in range(100)})
    s = make_splits(refs, seed=3, ratios=(0.7, 0.15, 0.15))
    total = len(refs)
    assert abs(len(s.train) / total - 0.70) < 0.10
    assert abs(len(s.test) / total - 0.15) < 0.10

@settings(max_examples=50, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=59),          # índice do artista
            st.sampled_from(["Rock", "Jazz", "Folk"]),        # gênero
            st.integers(min_value=1, max_value=5),            # faixas do artista
        ),
        min_size=20,
        max_size=60,
    )
)
def test_propriedade_disjuncao_de_artista_vale_para_qualquer_acervo(tuplas):
    """A disjunção não pode depender da forma do acervo — é invariante."""
    por_artista: dict[str, tuple[str, int]] = {}
    for idx, genero, n in tuplas:
        por_artista.setdefault(f"a{idx}", (genero, n))
    refs = _refs(por_artista)
    s = make_splits(refs, seed=11)
    indice = {r.track_id: r.artist_id for r in refs}
    conjuntos = [{indice[i] for i in ids} for ids in s.as_dict().values()]
    for i in range(len(conjuntos)):
        for j in range(i + 1, len(conjuntos)):
            assert conjuntos[i] & conjuntos[j] == set()
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest pipelines/tests/test_split.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_pipelines.split'`

- [ ] **Step 3: Implementar**

```python
# pipelines/src/youfy_pipelines/split.py
from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session
from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Feature, Track

log = structlog.get_logger()

NOMES = ("train", "val", "test")

@dataclass(frozen=True, slots=True)
class TrackRef:
    track_id: str
    artist_id: str
    genre: str

@dataclass
class Splits:
    train: list[str] = field(default_factory=list)
    val: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {"train": self.train, "val": self.val, "test": self.test}

def make_splits(
    refs: list[TrackRef],
    *,
    seed: int,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> Splits:
    """Particiona por artista, estratificando por gênero.

    Guloso por déficit: cada artista vai para o split que está mais abaixo da
    sua cota naquele gênero. A disjunção de artista sai por construção, já que
    um artista é atribuído uma única vez.
    """
    rng = random.Random(seed)
    saida = Splits()
    destinos = {"train": saida.train, "val": saida.val, "test": saida.test}

    por_genero: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in refs:
        por_genero[r.genre][r.artist_id].append(r.track_id)

    for genero in sorted(por_genero):
        artistas = por_genero[genero]
        total_do_genero = sum(len(v) for v in artistas.values())
        alvos = {nome: total_do_genero * p for nome, p in zip(NOMES, ratios)}
        atual = {nome: 0 for nome in NOMES}

        # Embaralha com a seed e depois ordena por tamanho. O sort do Python e
        # estavel, entao o embaralhamento sobrevive como criterio de desempate.
        ordem = sorted(artistas)
        rng.shuffle(ordem)
        ordem.sort(key=lambda a: -len(artistas[a]))

        for artista in ordem:
            escolhido = max(NOMES, key=lambda nome: (alvos[nome] - atual[nome], nome))
            faixas = sorted(artistas[artista])
            destinos[escolhido].extend(faixas)
            atual[escolhido] += len(faixas)

    for nome in NOMES:
        destinos[nome].sort()
    return saida

def splits_dir(data_dir: Path, spec: FeatureSpec) -> Path:
    return data_dir / "splits" / spec.fingerprint()

def run_split(
    session: Session,
    *,
    data_dir: Path,
    spec: FeatureSpec,
    seed: int = 42,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
) -> Splits:
    linhas = session.execute(
        select(Track.id, Track.artist_id, Track.top_genre)
        .join(Feature, Feature.track_id == Track.id)
        .where(Feature.spec_fingerprint == spec.fingerprint())
        .where(Feature.status == "ok")
        .where(Track.top_genre.is_not(None))
    ).all()
    refs = [TrackRef(tid, aid, genero) for tid, aid, genero in linhas]

    splits = make_splits(refs, seed=seed, ratios=ratios)
    destino = splits_dir(data_dir, spec)
    destino.mkdir(parents=True, exist_ok=True)
    for nome, ids in splits.as_dict().items():
        (destino / f"{nome}.json").write_text(
            json.dumps({"seed": seed, "fingerprint": spec.fingerprint(), "track_ids": ids}, indent=2)
        )

    log.info("split.concluido", seed=seed, train=len(splits.train),
             val=len(splits.val), test=len(splits.test))
    return splits
```

- [ ] **Step 4: Adicionar o comando à CLI**

```python
# pipelines/src/youfy_pipelines/cli.py  — acrescentar

from .split import run_split

@pipeline.command("split")
def split_cmd(
    data_dir: Path = typer.Option(None),
    seed: int = typer.Option(42),
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
) -> None:
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    with session_scope() as session:
        splits = run_split(session, data_dir=raiz, spec=spec, seed=seed)
    typer.echo(
        f"train={len(splits.train)} val={len(splits.val)} test={len(splits.test)}"
    )
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv run pytest pipelines/tests/test_split.py -v`
Expected: PASS nos 6 testes, incluindo o property-based

- [ ] **Step 6: Commitar**

```bash
git add pipelines
git commit -m "feat(pipelines): split agrupado por artista com invariante testado"
```

---

### Task 9: DVC, teste ponta a ponta e CI completo

**Files:**
- Create: `.dvc/config`, `.dvcignore`, `data/.gitkeep`
- Create: `pipelines/tests/test_pipeline_e2e.py`
- Modify: `Makefile` (alvos `e2e` e `dvc-repro`)
- Modify: `.github/workflows/ci.yml` (rodar o e2e)
- Modify: `pyproject.toml` (dependência `dvc`)
- Create: `README.md`

**Interfaces:**
- Consumes: `run_ingest` (Task 6), `run_featurize` (Task 7), `run_split` (Task 8), `build_fma_fixture` (Task 5).
- Produces: `make e2e` verde, e `data/features` + `data/splits` sob versionamento DVC.

- [ ] **Step 1: Escrever o teste ponta a ponta que falha**

```python
# pipelines/tests/test_pipeline_e2e.py
"""Atravessa ingest → featurize → split num micro-dump.

É o teste que pega o que os unitários não pegam: incompatibilidade entre
estágios e mudança de formato de artefato.
"""
import json

from youfy_audio.spec import FeatureSpec
from youfy_catalog.models import Track
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_pipelines.featurize import run_featurize
from youfy_pipelines.ingest import run_ingest
from youfy_pipelines.split import run_split, splits_dir


GENEROS = ["Rock", "Jazz", "Folk"]

def _micro_dump(tmp_path):
    faixas = []
    track_id = 2
    for g, genero in enumerate(GENEROS):
        for a in range(8):                       # 8 artistas por gênero
            for _ in range(3):                   # 3 faixas por artista
                faixas.append(FixtureTrack(track_id, g * 100 + a, f"Artista {g}-{a}", genero))
                track_id += 1
    faixas.append(FixtureTrack(track_id, 999, "Artista Ruim", "Rock", corrompido=True))
    build_fma_fixture(tmp_path, faixas)
    return len(faixas)

def test_pipeline_completo_no_micro_dump(session, tmp_path):
    total = _micro_dump(tmp_path)
    data_dir = tmp_path / "data"
    spec = FeatureSpec(n_mels=16, n_frames=20)

    ingest = run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    assert ingest.total == total
    assert ingest.failed == 1
    assert ingest.ingested == total - 1

    feat = run_featurize(session, data_dir=data_dir, spec=spec)
    session.flush()
    assert feat.computed == ingest.ingested
    assert feat.failed == 0

    splits = run_split(session, data_dir=data_dir, spec=spec, seed=42)
    assert len(splits.train) + len(splits.val) + len(splits.test) == ingest.ingested

    for nome, ids in splits.as_dict().items():
        payload = json.loads((splits_dir(data_dir, spec) / f"{nome}.json").read_text())
        assert payload["fingerprint"] == spec.fingerprint()
        assert payload["track_ids"] == ids

    # O invariante que mais importa, verificado tambem no encadeamento real.
    dono = {t.id: t.artist_id for t in session.query(Track).all()}
    conjuntos = [{dono[i] for i in ids} for ids in splits.as_dict().values()]
    assert conjuntos[0] & conjuntos[1] == set()
    assert conjuntos[0] & conjuntos[2] == set()
    assert conjuntos[1] & conjuntos[2] == set()

def test_pipeline_e_retomavel_a_partir_de_qualquer_estagio(session, tmp_path):
    _micro_dump(tmp_path)
    data_dir = tmp_path / "data"
    spec = FeatureSpec(n_mels=16, n_frames=20)

    run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    run_featurize(session, data_dir=data_dir, spec=spec)
    session.flush()

    # Reexecutar tudo não deve refazer trabalho nem mudar o resultado.
    segunda_feat = run_featurize(session, data_dir=data_dir, spec=spec)
    assert segunda_feat.computed == 0
    a = run_split(session, data_dir=data_dir, spec=spec, seed=42).as_dict()
    b = run_split(session, data_dir=data_dir, spec=spec, seed=42).as_dict()
    assert a == b
```

- [ ] **Step 2: Rodar o e2e**

Este teste é rede de regressão sobre comportamento que já existe, não um ciclo
red-green: os três estágios foram construídos nas Tasks 6 a 8. O resultado
esperado é PASS. Se falhar, o defeito é de **integração entre estágios** — que
é exatamente o que ele existe para revelar.

Run: `uv run pytest pipelines/tests/test_pipeline_e2e.py -v --durations=5`
Expected: PASS nos 2 testes, abaixo de 2 minutos

- [ ] **Step 3: Diagnosticar, se falhar**

Corrija sempre no estágio culpado, nunca no teste. Os três modos de falha prováveis:

| Sintoma | Causa provável |
|---|---|
| `feat.computed != ingest.ingested` | `run_featurize` lê faixas que `run_ingest` não gravou, ou vice-versa — divergência no formato de `Track.id` |
| Contagem do split menor que `ingest.ingested` | `run_split` filtra por `Feature.spec_fingerprint` e a `FeatureSpec` dos dois estágios não é a mesma config |
| Conjuntos de artista se cruzam | Regressão no `make_splits`; rode `pytest pipelines/tests/test_split.py` antes, para isolar |

- [ ] **Step 4: Inicializar o DVC**

```bash
uv add dvc
uv run dvc init
uv run dvc remote add -d local /tmp/youfy-dvc-remote
mkdir -p data && touch data/.gitkeep
uv run dvc add data/features data/splits
```

```
# .dvcignore
data/raw/
```

`data/raw/` fica de fora de propósito: o dump do FMA é imutável e grande, rastreado pelo manifesto de ingestão e pelo hash dos arquivos, não duplicado no DVC.

- [ ] **Step 5: Acrescentar os alvos ao Makefile**

```makefile
# Makefile — acrescentar

.PHONY: e2e dvc-push

e2e:
	uv run pytest pipelines/tests/test_pipeline_e2e.py -v

dvc-push:
	uv run dvc add data/features data/splits && uv run dvc push
```

- [ ] **Step 6: Rodar o CI completo e escrever o README**

Acrescente o passo do e2e ao `.github/workflows/ci.yml`, depois de `uv run pytest -v`:

```yaml
      - run: uv run pytest pipelines/tests/test_pipeline_e2e.py -v --durations=5
```

````markdown
# Youfy

Laboratório de IA aplicada no formato de um player de música, sobre catálogo
com licenciamento aberto (Free Music Archive).

**Plano atual:** 1A — Fundação de Dados.
Ver `docs/superpowers/specs/` e `docs/superpowers/plans/`.

## Começando

```bash
make setup      # instala dependências
make up         # sobe o Postgres local
make test       # roda a suíte
make e2e        # pipeline ponta a ponta no micro-dump
```

## Pipeline

```bash
youfy pipeline ingest --dump-dir ./data/raw/fma
youfy pipeline featurize
youfy pipeline split --seed 42
```
````

- [ ] **Step 7: Verificar tudo e commitar**

Run: `make lint && make test && make e2e`
Expected: ruff limpo; toda a suíte verde; e2e abaixo de 2 minutos

```bash
git add .dvc .dvcignore data/.gitkeep Makefile .github README.md \
        pipelines/tests/test_pipeline_e2e.py pyproject.toml uv.lock
git commit -m "test: pipeline ponta a ponta em ci e versionamento dvc das features"
```

---

## Verificação final do plano 1A

Ao terminar a Task 9, estes comandos devem passar numa máquina limpa:

```bash
make setup && make up
make lint && make test && make e2e
```

E, com o dump real do FMA em `data/raw/fma`:

```bash
youfy pipeline ingest --dump-dir ./data/raw/fma --audio-ext .mp3
youfy pipeline featurize
youfy pipeline split --seed 42
```

Mapeamento para os critérios de aceite da spec: este plano cobre os itens **1, 2 e 3** do §10. Os itens 4–12 pertencem aos planos 1B e 1C.

Da §9 da spec, o 1A entrega os logs estruturados em JSON e a quarentena de
ingestão. O comando `youfy doctor` fica para o 1C: só faz sentido quando houver
modelo promovido e eventos para reportar.

## O que o 1B vai consumir daqui

- `FeatureSpec` e seu `fingerprint()` — entram no artefato de modelo.
- `data/features/melspec/<fingerprint>/<track_id>.npy` — entrada do `Dataset`.
- `data/splits/<fingerprint>/{train,val,test}.json` — partições do treino.
- `Track.top_genre` — os rótulos.
