# Youfy 1B — Modelo e Serving: Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treinar um classificador de gênero rastreado no MLflow, promovê-lo por critério codificado e servi-lo com validação de `FeatureSpec` que recusa subir em caso de divergência.

**Architecture:** Dois pacotes novos com fronteira estrita. `ml` é biblioteca pura de treino e avaliação: recebe listas de `(track_id, rótulo)` e um diretório de arrays, e não sabe que existe banco de dados nem HTTP. `serving` resolve o modelo promovido no registry, valida a `FeatureSpec` embutida no artefato contra a config do featurizer e prediz. `pipelines` ganha dois comandos finos que fazem a ponte com o catálogo.

**Tech Stack:** PyTorch, scikit-learn, MLflow (tracking + registry, backend Postgres), numpy, Typer, pytest.

**Spec:** `docs/superpowers/specs/2026-09-18-youfy-loop-fechado-minimo-design.md`

**Depende de:** `docs/superpowers/plans/2026-09-18-youfy-1a-fundacao-de-dados.md`, já executado.

## Premissas declaradas

Este plano foi escrito antes de o `fma_small` real ter sido processado. Duas
entradas são premissa, não medida, e devem ser conferidas na Task 4:

1. **Batch de 32 cabe em memória** com melspec de `(128, 1292)` em `float32`
   (~660 KB por amostra, ~21 MB por batch). Se não couber, reduza o batch antes
   de mexer em qualquer outra coisa — a arquitetura não muda.
2. **Uma época sobre 8.000 faixas é tolerável em CPU.** Se não for, o caminho é
   pré-carregar os arrays em memória (7 GB não cabem; 8.000 × 660 KB = 5,3 GB
   também não), então a alternativa real é reduzir `n_frames` na `FeatureSpec` —
   o que muda o fingerprint e força refeaturizar. Decida isso antes da Task 4,
   não depois.

## Desvio explícito da spec

A spec (§5.1) fala em promover o modelo para o **stage** `Production`. Stages do
MLflow Model Registry estão descontinuados desde a série 2.9 em favor de
**aliases**. Este plano usa o alias `production`, via
`MlflowClient.set_registered_model_alias`. O comportamento exigido pela spec —
um ponteiro único para o modelo vigente, trocado por critério codificado — é
idêntico; só o mecanismo é o suportado.

## Global Constraints

Valem todas as do plano 1A, mais:

- `ml` **não importa** `youfy_catalog`, `youfy_serving`, `youfy_pipelines`. Ele treina a partir de um diretório de arrays e uma lista de rótulos.
- `serving` **não sabe** como o modelo foi treinado. Consome registry e artefato, nada mais.
- Ordem canônica de classes vive **dentro do artefato**, nunca num dicionário externo.
- Gate de promoção: `macro_f1_novo >= macro_f1_campeao + 0.005`. Sem campeão: `macro_f1 >= 0.40`.
- Reprodutibilidade: mesma seed e mesmo dado → macro-F1 dentro de **±0,002**.
- Rótulos embaralhados: macro-F1 **≤ 0,20** com **8 classes** balanceadas (acaso = 0,125). Os testes sintéticos usam 8 classes justamente para que o limiar seja o mesmo da spec.
- Nos testes, `num_workers=0` e `generator` semeado no DataLoader. Sem isso não há determinismo.
- Tracking dos testes: `sqlite:///<tmp_path>/mlflow.db`. O file store do MLflow **não** suporta Model Registry; sqlite suporta.
- Trabalhe numa branch de feature. Commits sem identificação de IA.

---

### Task 1: MLflow local e o contrato do artefato

**Files:**
- Modify: `docker-compose.yml`, `Makefile`, `.env.example`
- Create: `infra/postgres/initdb/10-mlflow.sql`
- Create: `packages/ml/pyproject.toml`, `packages/ml/src/youfy_ml/__init__.py`
- Create: `packages/ml/src/youfy_ml/artifact.py`
- Create: `packages/ml/tests/test_artifact.py`
- Modify: `pyproject.toml` (membro do workspace)

**Interfaces:**
- Consumes: `FeatureSpec` de `youfy_audio.spec` (1A).
- Produces:
  - `GenreClassifier` — Protocol com `feature_spec: FeatureSpec`, `classes: list[str]`, `predict(melspec: np.ndarray) -> np.ndarray`.
  - `TorchGenreClassifier(module, feature_spec, classes)` implementando o Protocol, com `save(dir: Path) -> None` e `load(dir: Path) -> TorchGenreClassifier` (classmethod).

- [x] **Step 1: Escrever os testes que falham**

```python
# packages/ml/tests/test_artifact.py
import numpy as np
import pytest
import torch
from torch import nn
from youfy_audio.spec import FeatureSpec
from youfy_ml.artifact import GenreClassifier, TorchGenreClassifier

CLASSES = ["Electronic", "Folk", "Hip-Hop", "Instrumental", "International", "Pop", "Rock", "Experimental"]


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
```

- [x] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/ml/tests/test_artifact.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_ml'`

- [x] **Step 3: Criar o pacote `ml` no workspace**

```toml
# packages/ml/pyproject.toml
[project]
name = "youfy-ml"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "youfy-audio",
  "torch>=2.3",
  "numpy>=1.26",
  "scikit-learn>=1.5",
  "mlflow>=2.13",
]

[tool.uv.sources]
youfy-audio = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Acrescente `youfy-ml` em `dependencies` e em `[tool.uv.sources]` do `pyproject.toml` da raiz, no mesmo formato dos outros três.

- [x] **Step 4: Implementar o contrato do artefato**

```python
# packages/ml/src/youfy_ml/artifact.py
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import torch
from torch import nn
from youfy_audio.spec import FeatureSpec


@runtime_checkable
class GenreClassifier(Protocol):
    """Contrato entre `ml` e `serving`.

    O artefato carrega a própria `FeatureSpec`: o serving não tem permissão de
    assumir que sabe featurizar. É o que converte training/serving skew de
    degradação silenciosa em falha ruidosa na carga.
    """

    feature_spec: FeatureSpec
    classes: list[str]

    def predict(self, melspec: np.ndarray) -> np.ndarray: ...


class TorchGenreClassifier:
    ARQUIVO_PESOS = "pesos.pt"
    ARQUIVO_META = "metadados.json"

    def __init__(self, module: nn.Module, feature_spec: FeatureSpec, classes: list[str]) -> None:
        if not classes:
            raise ValueError("classes nao pode ser vazio: a ordem canonica vive no artefato")
        self.module = module
        self.feature_spec = feature_spec
        self.classes = list(classes)

    def predict(self, melspec: np.ndarray) -> np.ndarray:
        esperado = (self.feature_spec.n_mels, self.feature_spec.n_frames)
        if melspec.shape != esperado:
            raise ValueError(f"shape {melspec.shape} incompativel com a spec do modelo {esperado}")
        self.module.eval()
        with torch.no_grad():
            entrada = torch.from_numpy(np.asarray(melspec, dtype=np.float32))[None, None, :, :]
            logits = self.module(entrada)
            probs = torch.softmax(logits, dim=-1)[0]
        return probs.numpy().astype(np.float32)

    def save(self, destino: Path) -> None:
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        torch.save(self.module, destino / self.ARQUIVO_PESOS)
        (destino / self.ARQUIVO_META).write_text(
            json.dumps(
                {"feature_spec": asdict(self.feature_spec), "classes": self.classes}, indent=2
            )
        )

    @classmethod
    def load(cls, origem: Path) -> TorchGenreClassifier:
        origem = Path(origem)
        meta = json.loads((origem / cls.ARQUIVO_META).read_text())
        modulo = torch.load(origem / cls.ARQUIVO_PESOS, weights_only=False)
        return cls(
            module=modulo,
            feature_spec=FeatureSpec(**meta["feature_spec"]),
            classes=meta["classes"],
        )
```

- [x] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv sync --all-extras && uv run pytest packages/ml/tests/test_artifact.py -v`
Expected: PASS nos 6 testes

- [x] **Step 6: Subir o MLflow no compose**

O MLflow precisa de um banco próprio: misturá-lo ao `youfy` faria o `alembic check`
do CI ver as tabelas do MLflow como remoções pendentes e quebrar.

```sql
-- infra/postgres/initdb/10-mlflow.sql
SELECT 'CREATE DATABASE mlflow' WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'mlflow'
)\gexec
```

```yaml
# docker-compose.yml — acrescentar ao serviço postgres e criar o mlflow
services:
  postgres:
    volumes:
      - "pgdata:/var/lib/postgresql/data"
      - "./infra/postgres/initdb:/docker-entrypoint-initdb.d:ro"

  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.17.2
    depends_on:
      postgres:
        condition: service_healthy
    command: >
      bash -c "pip install --quiet psycopg2-binary &&
      mlflow server --host 0.0.0.0 --port 5000
      --backend-store-uri postgresql://youfy:youfy@postgres:5432/mlflow
      --default-artifact-root /mlruns"
    ports: ["5000:5000"]
    volumes: ["mlruns:/mlruns"]

volumes:
  pgdata:
  mlruns:
```

O script de `initdb` só roda em volume novo. Como o seu `pgdata` já existe, crie o
banco uma vez com o alvo abaixo:

```makefile
# Makefile — acrescentar, e incluir os nomes em .PHONY

mlflow-db:
	docker compose exec -T postgres psql -U youfy -d postgres -tc \
	  "SELECT 1 FROM pg_database WHERE datname='mlflow'" | grep -q 1 || \
	  docker compose exec -T postgres psql -U youfy -d postgres -c "CREATE DATABASE mlflow"

mlflow-up: mlflow-db
	docker compose up -d --wait mlflow
```

```bash
# .env.example — acrescentar
YOUFY_MLFLOW_TRACKING_URI=http://localhost:5000
YOUFY_MODEL_NAME=youfy-genre-clf
```

- [x] **Step 7: Verificar e commitar**

Run: `make up && make mlflow-up && curl -sf http://localhost:5000/health && make lint && make test`
Expected: MLflow responde `OK`; lint limpo; toda a suíte anterior ainda verde

```bash
git add packages/ml pyproject.toml uv.lock docker-compose.yml Makefile .env.example infra
git commit -m "feat(ml): contrato do artefato de modelo e mlflow local no compose"
```

---

### Task 2: `ml.dataset` — leitura dos arrays com rótulos

**Files:**
- Create: `packages/ml/src/youfy_ml/dataset.py`
- Create: `packages/ml/src/youfy_ml/testing.py`
- Create: `packages/ml/tests/test_dataset.py`

**Interfaces:**
- Consumes: `FeatureSpec` (1A); layout `data/features/melspec/<fingerprint>/<track_id com ':' virado '_'>.npy` (1A, Task 7).
- Produces:
  - `LabeledTrack(track_id: str, label: str)` — dataclass congelada.
  - `MelspecDataset(samples: list[LabeledTrack], *, features_dir: Path, classes: list[str])` — argumentos nomeados depois de `samples` — `torch.utils.data.Dataset`, devolve `(tensor (1, n_mels, n_frames), índice da classe)`.
  - `MissingFeature(Exception)`.
  - `escrever_features(destino, *, n_classes=8, por_classe=24, n_mels=16, n_frames=20, seed=0, embaralhar_rotulos=False) -> tuple[list[LabeledTrack], list[str]]` — vive em `src/youfy_ml/testing.py`, **nao** em `tests/`, porque e importado por testes de `serving`; `packages/ml/tests/` nao e um pacote importavel.

O dataset **não** consulta banco: recebe os rótulos prontos. É o que mantém `ml` treinável a partir de um diretório de arrays.

- [x] **Step 1: Escrever o gerador sintético e os testes que falham**

```python
# packages/ml/src/youfy_ml/testing.py
"""Acervo sintético com sinal aprendível, para testes de ML rápidos.

Cada classe concentra energia numa faixa distinta do melspec, então um modelo
sadio aprende; com rótulos embaralhados não há o que aprender, e a métrica
volta para o acaso. São 8 classes de propósito: é o número da spec, e o que
faz o limiar de 0,20 do teste de rótulos embaralhados ser o mesmo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from youfy_ml.dataset import LabeledTrack


def escrever_features(
    destino: Path,
    *,
    n_classes: int = 8,
    por_classe: int = 24,
    n_mels: int = 16,
    n_frames: int = 20,
    seed: int = 0,
    embaralhar_rotulos: bool = False,
) -> tuple[list[LabeledTrack], list[str]]:
    destino.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    classes = [f"g{k}" for k in range(n_classes)]
    amostras: list[LabeledTrack] = []
    verdadeiros: list[int] = []

    largura = max(1, n_mels // n_classes)
    for k in range(n_classes):
        for i in range(por_classe):
            arr = rng.normal(0.0, 1.0, size=(n_mels, n_frames)).astype(np.float32)
            inicio = k * largura
            arr[inicio : inicio + largura, :] += 8.0      # a banda que identifica a classe
            track_id = f"fma_track_{k}_{i}"
            np.save(destino / f"{track_id}.npy", arr)
            amostras.append(LabeledTrack(track_id, classes[k]))
            verdadeiros.append(k)

    if embaralhar_rotulos:
        permutados = rng.permutation(verdadeiros)
        amostras = [
            LabeledTrack(a.track_id, classes[int(k)]) for a, k in zip(amostras, permutados)
        ]
    return amostras, classes
```

```python
# packages/ml/tests/test_dataset.py
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
```

- [x] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/ml/tests/test_dataset.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_ml.dataset'`

- [x] **Step 3: Implementar**

```python
# packages/ml/src/youfy_ml/dataset.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class MissingFeature(Exception):
    """Array de feature ausente para uma faixa que o split declarou existir."""


@dataclass(frozen=True, slots=True)
class LabeledTrack:
    track_id: str
    label: str


class MelspecDataset(Dataset):
    """Lê `<features_dir>/<track_id>.npy` e devolve `(tensor, indice da classe)`.

    Não consulta banco: recebe os rótulos prontos. É o que mantém `ml`
    treinável a partir de um diretório de arrays.
    """

    def __init__(
        self, samples: list[LabeledTrack], *, features_dir: Path, classes: list[str]
    ) -> None:
        desconhecidos = {a.label for a in samples} - set(classes)
        if desconhecidos:
            raise ValueError(f"rotulos fora das classes canonicas: {sorted(desconhecidos)}")
        self.samples = list(samples)
        self.features_dir = Path(features_dir)
        self.classes = list(classes)
        self._indice = {c: i for i, c in enumerate(self.classes)}

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, int]:
        amostra = self.samples[i]
        caminho = self.features_dir / f"{amostra.track_id}.npy"
        if not caminho.exists():
            raise MissingFeature(f"feature ausente para {amostra.track_id}: {caminho}")
        arr = np.load(caminho).astype(np.float32)
        return torch.from_numpy(arr)[None, :, :], self._indice[amostra.label]
```

- [x] **Step 4: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/ml/tests -v`
Expected: PASS nos 12 testes (6 de artifact + 6 de dataset)

- [x] **Step 5: Commitar**

```bash
git add packages/ml
git commit -m "feat(ml): dataset de melspec desacoplado do catalogo"
```

---

### Task 3: `ml.model` — a CNN e o semeador determinístico

**Files:**
- Create: `packages/ml/src/youfy_ml/model.py`
- Create: `packages/ml/src/youfy_ml/seeding.py`
- Create: `packages/ml/tests/test_model.py`
- Create: `packages/ml/tests/test_seeding.py`

**Interfaces:**
- Consumes: nada de outros pacotes.
- Produces:
  - `GenreCNN(n_classes: int, channels: tuple[int, ...] = (16, 32, 64))` — `nn.Module`, entrada `(B, 1, n_mels, n_frames)`, saída `(B, n_classes)`.
  - `set_seed(seed: int) -> None` — semeia `random`, `numpy`, `torch`, CUDA, e liga algoritmos determinísticos.
  - `seeded_generator(seed: int) -> torch.Generator`
  - `worker_init(worker_id: int) -> None`

A CNN termina em `AdaptiveAvgPool2d(1)`, o que a torna **independente de `n_mels` e `n_frames`**. Isso elimina aritmética de shape na cabeça — a classe de bug mais chata de depurar quando se muda a `FeatureSpec`.

- [x] **Step 1: Escrever os testes que falham**

```python
# packages/ml/tests/test_model.py
import torch
from youfy_ml.model import GenreCNN
from youfy_ml.seeding import set_seed


def test_forward_devolve_logits_por_classe():
    modelo = GenreCNN(n_classes=8)
    saida = modelo(torch.zeros(4, 1, 16, 20))
    assert saida.shape == (4, 8)


def test_e_independente_das_dimensoes_do_melspec():
    """AdaptiveAvgPool na saída: mudar a FeatureSpec não exige mexer na cabeça."""
    modelo = GenreCNN(n_classes=8)
    assert modelo(torch.zeros(2, 1, 16, 20)).shape == (2, 8)
    assert modelo(torch.zeros(2, 1, 128, 1292)).shape == (2, 8)


def test_mesma_seed_produz_os_mesmos_pesos_iniciais():
    set_seed(7)
    a = GenreCNN(n_classes=8)
    set_seed(7)
    b = GenreCNN(n_classes=8)
    for pa, pb in zip(a.parameters(), b.parameters()):
        assert torch.equal(pa, pb)


def test_seeds_diferentes_produzem_pesos_diferentes():
    set_seed(1)
    a = GenreCNN(n_classes=8)
    set_seed(2)
    b = GenreCNN(n_classes=8)
    assert not all(torch.equal(pa, pb) for pa, pb in zip(a.parameters(), b.parameters()))


def test_em_modo_eval_aceita_batch_unitario():
    """BatchNorm em treino estoura com batch 1; o serving sempre prediz de um em um."""
    modelo = GenreCNN(n_classes=8)
    modelo.eval()
    with torch.no_grad():
        assert modelo(torch.zeros(1, 1, 16, 20)).shape == (1, 8)
```

```python
# packages/ml/tests/test_seeding.py
import random

import numpy as np
import torch
from youfy_ml.seeding import seeded_generator, set_seed


def test_semeia_as_tres_fontes_de_aleatoriedade():
    set_seed(42)
    trio_a = (random.random(), float(np.random.rand()), float(torch.rand(1)))
    set_seed(42)
    trio_b = (random.random(), float(np.random.rand()), float(torch.rand(1)))
    assert trio_a == trio_b


def test_generator_semeado_e_reprodutivel():
    a = torch.randperm(100, generator=seeded_generator(3))
    b = torch.randperm(100, generator=seeded_generator(3))
    assert torch.equal(a, b)


def test_liga_algoritmos_deterministicos():
    set_seed(1)
    assert torch.are_deterministic_algorithms_enabled()
```

- [x] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/ml/tests/test_model.py packages/ml/tests/test_seeding.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_ml.model'`

- [x] **Step 3: Implementar o semeador**

```python
# packages/ml/src/youfy_ml/seeding.py
from __future__ import annotations

import os
import random

import numpy as np
import torch


def set_seed(seed: int) -> None:
    """Semeia tudo e liga algoritmos determinísticos.

    Sem isso o critério de reprodutibilidade da spec (±0,002 de macro-F1) não
    se sustenta: a ordem do dataloader e os kernels do cuDNN variam entre
    execuções e a métrica se move sozinha.
    """
    # Exigido pelo cuBLAS quando algoritmos determinísticos estão ligados.
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def seeded_generator(seed: int) -> torch.Generator:
    g = torch.Generator()
    g.manual_seed(seed)
    return g


def worker_init(worker_id: int) -> None:
    semente = torch.initial_seed() % 2**32
    np.random.seed(semente + worker_id)
    random.seed(semente + worker_id)
```

- [x] **Step 4: Implementar a CNN**

```python
# packages/ml/src/youfy_ml/model.py
from __future__ import annotations

import torch
from torch import nn


class GenreCNN(nn.Module):
    """CNN pequena sobre mel-espectrograma.

    Termina em AdaptiveAvgPool2d(1), então é independente de `n_mels` e
    `n_frames` — mudar a FeatureSpec não obriga a recalcular a cabeça.
    """

    def __init__(self, n_classes: int, channels: tuple[int, ...] = (16, 32, 64)) -> None:
        super().__init__()
        camadas: list[nn.Module] = []
        entrada = 1
        for c in channels:
            camadas += [
                nn.Conv2d(entrada, c, kernel_size=3, padding=1),
                nn.BatchNorm2d(c),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
            ]
            entrada = c
        self.features = nn.Sequential(*camadas)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(entrada, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.features(x)
        h = self.pool(h).flatten(1)
        return self.head(h)
```

- [x] **Step 5: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/ml/tests -v`
Expected: PASS nos 20 testes

- [x] **Step 6: Commitar**

```bash
git add packages/ml
git commit -m "feat(ml): cnn de genero independente de shape e semeadura determinista"
```

---

### Task 4: `ml.train` — loop de treino e as duas propriedades de ML

**Files:**
- Create: `packages/ml/src/youfy_ml/train.py`
- Create: `packages/ml/tests/test_train.py`

**Interfaces:**
- Consumes: `MelspecDataset`/`LabeledTrack` (Task 2); `GenreCNN`, `set_seed`, `seeded_generator`, `worker_init` (Task 3); `TorchGenreClassifier` (Task 1); `FeatureSpec` (1A).
- Produces:
  - `TrainConfig(seed:int=42, epochs:int=10, batch_size:int=32, lr:float=1e-3, channels:tuple[int,...]=(16,32,64), num_workers:int=0)` — dataclass congelada.
  - `EpochMetrics(epoch:int, train_loss:float, train_acc:float, val_loss:float, val_acc:float)`
  - `TrainResult(classifier: TorchGenreClassifier, history: list[EpochMetrics], final_train_acc: float)`
  - `train(config, *, train_samples, val_samples, features_dir, classes, feature_spec) -> TrainResult`

**Confira aqui as premissas declaradas no topo do plano**: com a `FeatureSpec` real
(`128×1292`), meça o tempo de uma época e o pico de memória com `batch_size=32`
antes de seguir. Ajustar `batch_size` é trivial; descobrir na Task 9 que não cabe,
não é.

- [ ] **Step 1: Escrever os testes que falham**

```python
# packages/ml/tests/test_train.py
import pytest
from youfy_audio.spec import FeatureSpec
from youfy_ml.train import TrainConfig, train

from youfy_ml.testing import escrever_features

SPEC = FeatureSpec(n_mels=16, n_frames=20)


def _treinar(tmp_path, *, seed=42, epochs=8, embaralhar=False, por_classe=24):
    amostras, classes = escrever_features(
        tmp_path, n_classes=8, por_classe=por_classe, n_mels=16, n_frames=20,
        seed=0, embaralhar_rotulos=embaralhar,
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
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/ml/tests/test_train.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_ml.train'`

- [ ] **Step 3: Implementar**

```python
# packages/ml/src/youfy_ml/train.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from youfy_audio.spec import FeatureSpec

from .artifact import TorchGenreClassifier
from .dataset import LabeledTrack, MelspecDataset
from .model import GenreCNN
from .seeding import seeded_generator, set_seed, worker_init


@dataclass(frozen=True, slots=True)
class TrainConfig:
    seed: int = 42
    epochs: int = 10
    batch_size: int = 32
    lr: float = 1e-3
    channels: tuple[int, ...] = (16, 32, 64)
    num_workers: int = 0


@dataclass(frozen=True, slots=True)
class EpochMetrics:
    epoch: int
    train_loss: float
    train_acc: float
    val_loss: float
    val_acc: float


@dataclass
class TrainResult:
    classifier: TorchGenreClassifier
    history: list[EpochMetrics] = field(default_factory=list)
    final_train_acc: float = 0.0


def train(
    config: TrainConfig,
    *,
    train_samples: list[LabeledTrack],
    val_samples: list[LabeledTrack],
    features_dir: Path,
    classes: list[str],
    feature_spec: FeatureSpec,
) -> TrainResult:
    if config.num_workers != 0:
        raise ValueError(
            "num_workers deve ser 0: workers paralelos quebram a reprodutibilidade "
            "exigida pelo criterio 11 da spec"
        )

    set_seed(config.seed)
    gerador = seeded_generator(config.seed)

    ds_train = MelspecDataset(train_samples, features_dir=features_dir, classes=classes)
    ds_val = MelspecDataset(val_samples, features_dir=features_dir, classes=classes)
    dl_train = DataLoader(
        ds_train, batch_size=config.batch_size, shuffle=True, generator=gerador,
        num_workers=0, worker_init_fn=worker_init, drop_last=False,
    )
    dl_val = DataLoader(ds_val, batch_size=config.batch_size, shuffle=False, num_workers=0)

    modelo = GenreCNN(n_classes=len(classes), channels=config.channels)
    otimizador = torch.optim.Adam(modelo.parameters(), lr=config.lr)
    criterio = nn.CrossEntropyLoss()

    historico: list[EpochMetrics] = []
    acc_treino = 0.0
    for epoca in range(config.epochs):
        perda_treino, acc_treino = _passo(modelo, dl_train, criterio, otimizador)
        perda_val, acc_val = _passo(modelo, dl_val, criterio, otimizador=None)
        historico.append(
            EpochMetrics(epoca, perda_treino, acc_treino, perda_val, acc_val)
        )

    classificador = TorchGenreClassifier(
        module=modelo, feature_spec=feature_spec, classes=classes
    )
    return TrainResult(classifier=classificador, history=historico, final_train_acc=acc_treino)


def _passo(modelo, loader, criterio, otimizador) -> tuple[float, float]:
    treinando = otimizador is not None
    modelo.train(treinando)
    soma_perda = acertos = total = 0.0

    with torch.set_grad_enabled(treinando):
        for x, y in loader:
            logits = modelo(x)
            perda = criterio(logits, y)
            if treinando:
                otimizador.zero_grad(set_to_none=True)
                perda.backward()
                otimizador.step()
            soma_perda += float(perda) * len(y)
            acertos += float((logits.argmax(dim=-1) == y).sum())
            total += len(y)

    return soma_perda / total, acertos / total
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/ml/tests/test_train.py -v --durations=5`
Expected: PASS nos 6 testes

- [ ] **Step 5: Medir as premissas com a FeatureSpec real**

```bash
uv run python - <<'EOF'
import time, numpy as np, torch
from youfy_ml.model import GenreCNN
x = torch.from_numpy(np.zeros((32, 1, 128, 1292), dtype=np.float32))
m = GenreCNN(n_classes=8)
t0 = time.perf_counter(); m(x); print(f"forward batch32 128x1292: {time.perf_counter()-t0:.2f}s")
print(f"memoria do batch: {x.element_size() * x.nelement() / 1e6:.0f} MB")
EOF
```

Anote os dois números no commit. Se o forward passar de poucos segundos, ajuste
`batch_size` ou `n_frames` **agora**, antes da Task 9.

- [ ] **Step 6: Commitar**

```bash
git add packages/ml
git commit -m "feat(ml): loop de treino deterministico com testes de reprodutibilidade e overfit"
```

---

### Task 5: `ml.evaluate` — métricas e o teste de rótulos embaralhados

**Files:**
- Create: `packages/ml/src/youfy_ml/evaluate.py`
- Create: `packages/ml/tests/test_evaluate.py`

**Interfaces:**
- Consumes: `TorchGenreClassifier` (Task 1); `MelspecDataset`/`LabeledTrack` (Task 2); `train`/`TrainConfig` (Task 4).
- Produces:
  - `Metrics(macro_f1: float, accuracy: float, per_class_f1: dict[str, float], confusion: list[list[int]])` — dataclass congelada, com `as_flat_dict() -> dict[str, float]` para o MLflow.
  - `evaluate(classifier, *, samples, features_dir) -> Metrics`

- [ ] **Step 1: Escrever os testes que falham**

```python
# packages/ml/tests/test_evaluate.py
from youfy_audio.spec import FeatureSpec
from youfy_ml.evaluate import evaluate
from youfy_ml.train import TrainConfig, train

from youfy_ml.testing import escrever_features

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
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/ml/tests/test_evaluate.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_ml.evaluate'`

- [ ] **Step 3: Implementar**

```python
# packages/ml/src/youfy_ml/evaluate.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from .artifact import GenreClassifier
from .dataset import LabeledTrack


@dataclass(frozen=True, slots=True)
class Metrics:
    macro_f1: float
    accuracy: float
    per_class_f1: dict[str, float]
    confusion: list[list[int]]

    def as_flat_dict(self) -> dict[str, float]:
        plano = {"macro_f1": self.macro_f1, "accuracy": self.accuracy}
        plano.update({f"f1__{c}": v for c, v in self.per_class_f1.items()})
        return plano


def evaluate(
    classifier: GenreClassifier, *, samples: list[LabeledTrack], features_dir: Path
) -> Metrics:
    features_dir = Path(features_dir)
    indice = {c: i for i, c in enumerate(classifier.classes)}

    verdadeiros: list[int] = []
    preditos: list[int] = []
    for amostra in samples:
        arr = np.load(features_dir / f"{amostra.track_id}.npy").astype(np.float32)
        verdadeiros.append(indice[amostra.label])
        preditos.append(int(np.argmax(classifier.predict(arr))))

    rotulos = list(range(len(classifier.classes)))
    f1_por_classe = f1_score(
        verdadeiros, preditos, labels=rotulos, average=None, zero_division=0
    )
    return Metrics(
        macro_f1=float(
            f1_score(verdadeiros, preditos, labels=rotulos, average="macro", zero_division=0)
        ),
        accuracy=float(accuracy_score(verdadeiros, preditos)),
        per_class_f1={c: float(v) for c, v in zip(classifier.classes, f1_por_classe)},
        confusion=confusion_matrix(verdadeiros, preditos, labels=rotulos).tolist(),
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/ml/tests/test_evaluate.py -v --durations=5`
Expected: PASS nos 4 testes

- [ ] **Step 5: Commitar**

```bash
git add packages/ml
git commit -m "feat(ml): metricas de avaliacao e teste de rotulos embaralhados"
```

---

### Task 6: `ml.promotion` — o gate codificado

**Files:**
- Create: `packages/ml/src/youfy_ml/promotion.py`
- Create: `packages/ml/tests/test_promotion.py`

**Interfaces:**
- Consumes: `Metrics` (Task 5).
- Produces:
  - `PromotionDecision(promote: bool, reason: str, challenger_f1: float, champion_f1: float | None)`
  - `should_promote(challenger: Metrics, champion: Metrics | None, *, margin: float = 0.005, floor: float = 0.40) -> PromotionDecision`

Função pura, sem I/O. É o coração do gate da spec, e por ser pura dá para testá-la
exaustivamente — inclusive nos limites, que é onde um gate mal escrito promove ruído.

- [ ] **Step 1: Escrever os testes que falham**

```python
# packages/ml/tests/test_promotion.py
import pytest
from youfy_ml.evaluate import Metrics
from youfy_ml.promotion import should_promote


def _m(f1: float) -> Metrics:
    return Metrics(macro_f1=f1, accuracy=f1, per_class_f1={}, confusion=[])


def test_sem_campeao_promove_acima_do_piso():
    d = should_promote(_m(0.41), None)
    assert d.promote is True
    assert d.champion_f1 is None
    assert "piso" in d.reason


def test_sem_campeao_rejeita_abaixo_do_piso():
    assert should_promote(_m(0.39), None).promote is False


def test_sem_campeao_o_piso_e_inclusivo():
    assert should_promote(_m(0.40), None).promote is True


def test_promove_quando_supera_o_campeao_pela_margem():
    assert should_promote(_m(0.705), _m(0.70)).promote is True


def test_rejeita_empate_com_o_campeao():
    d = should_promote(_m(0.70), _m(0.70))
    assert d.promote is False
    assert "margem" in d.reason


def test_rejeita_ganho_dentro_da_margem():
    """0,4 p.p. de ganho é ruído de seed, não melhoria. Promover aqui trocaria
    o campeão por acaso e envenenaria toda comparação futura."""
    assert should_promote(_m(0.704), _m(0.70)).promote is False


def test_a_margem_e_inclusiva_no_limite_exato():
    assert should_promote(_m(0.705), _m(0.700)).promote is True


def test_rejeita_quando_pior_que_o_campeao():
    assert should_promote(_m(0.60), _m(0.70)).promote is False


def test_com_campeao_o_piso_nao_se_aplica():
    """Campeão fraco não trava a sucessão: o critério passa a ser relativo."""
    assert should_promote(_m(0.31), _m(0.30)).promote is True


def test_decisao_carrega_os_dois_numeros_para_o_relatorio():
    d = should_promote(_m(0.80), _m(0.70))
    assert d.challenger_f1 == pytest.approx(0.80)
    assert d.champion_f1 == pytest.approx(0.70)


def test_margem_e_piso_sao_configuraveis():
    assert should_promote(_m(0.71), _m(0.70), margin=0.05).promote is False
    assert should_promote(_m(0.50), None, floor=0.60).promote is False
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/ml/tests/test_promotion.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_ml.promotion'`

- [ ] **Step 3: Implementar**

```python
# packages/ml/src/youfy_ml/promotion.py
from __future__ import annotations

from dataclasses import dataclass

from .evaluate import Metrics


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    promote: bool
    reason: str
    challenger_f1: float
    champion_f1: float | None


def should_promote(
    challenger: Metrics,
    champion: Metrics | None,
    *,
    margin: float = 0.005,
    floor: float = 0.40,
) -> PromotionDecision:
    """Gate de promoção da spec, §5.1.

    A margem existe para não trocar o campeão por ruído de seed: um ganho de
    0,4 p.p. entre duas execuções não é melhoria, e promover em cima disso
    envenena toda comparação futura.
    """
    desafiante = challenger.macro_f1

    if champion is None:
        aprovado = desafiante >= floor
        return PromotionDecision(
            promote=aprovado,
            reason=(
                f"sem campeao; macro_f1={desafiante:.4f} "
                f"{'atinge' if aprovado else 'nao atinge'} o piso de {floor:.4f}"
            ),
            challenger_f1=desafiante,
            champion_f1=None,
        )

    vigente = champion.macro_f1
    exigido = vigente + margin
    aprovado = desafiante >= exigido
    return PromotionDecision(
        promote=aprovado,
        reason=(
            f"macro_f1={desafiante:.4f} contra campeao={vigente:.4f}; "
            f"{'supera' if aprovado else 'nao supera'} a margem de {margin:.4f} "
            f"(exigido >= {exigido:.4f})"
        ),
        challenger_f1=desafiante,
        champion_f1=vigente,
    )
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/ml/tests/test_promotion.py -v`
Expected: PASS nos 11 testes

- [ ] **Step 5: Commitar**

```bash
git add packages/ml
git commit -m "feat(ml): gate de promocao codificado com margem contra ruido de seed"
```

---

### Task 7: `ml.tracking` — run do MLflow e registro por alias

**Files:**
- Create: `packages/ml/src/youfy_ml/tracking.py`
- Create: `packages/ml/tests/test_tracking.py`

**Interfaces:**
- Consumes: `TrainConfig`/`TrainResult` (Task 4); `Metrics` (Task 5); `TorchGenreClassifier` (Task 1).
- Produces:
  - `ALIAS_PRODUCAO = "production"`
  - `RunInfo(run_id: str, model_version: str | None)`
  - `log_run(*, tracking_uri, experiment, config, result, metrics, register_as) -> RunInfo` — loga params, métricas por época, métricas finais e o artefato; registra uma versão nova.
  - `promote(*, tracking_uri, model_name, version) -> None` — aponta o alias `production`.
  - `load_champion_metrics(*, tracking_uri, model_name) -> Metrics | None` — lê as métricas da versão sob o alias; `None` se não houver.

Os testes usam `sqlite:///<tmp>/mlflow.db`: o **file store do MLflow não suporta
Model Registry**, então tracking em arquivo simples não serviria aqui.

- [ ] **Step 1: Escrever os testes que falham**

```python
# packages/ml/tests/test_tracking.py
import mlflow
import pytest
from mlflow.tracking import MlflowClient
from youfy_audio.spec import FeatureSpec
from youfy_ml.evaluate import Metrics
from youfy_ml.tracking import ALIAS_PRODUCAO, load_champion_metrics, log_run, promote
from youfy_ml.train import TrainConfig, train

from youfy_ml.testing import escrever_features

SPEC = FeatureSpec(n_mels=16, n_frames=20)
MODELO = "youfy-genre-clf"


@pytest.fixture
def tracking_uri(tmp_path):
    return f"sqlite:///{tmp_path / 'mlflow.db'}"


@pytest.fixture
def resultado(tmp_path):
    amostras, classes = escrever_features(tmp_path, n_classes=8, por_classe=4, n_mels=16, n_frames=20)
    return train(
        TrainConfig(seed=0, epochs=2, batch_size=8),
        train_samples=amostras, val_samples=amostras,
        features_dir=tmp_path, classes=classes, feature_spec=SPEC,
    )


def _metricas(f1: float) -> Metrics:
    return Metrics(macro_f1=f1, accuracy=f1, per_class_f1={"g0": f1}, confusion=[[1]])


def test_log_run_registra_params_metricas_e_artefato(tracking_uri, resultado):
    info = log_run(
        tracking_uri=tracking_uri, experiment="teste",
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        result=resultado, metrics=_metricas(0.7), register_as=MODELO,
    )
    mlflow.set_tracking_uri(tracking_uri)
    run = MlflowClient().get_run(info.run_id)
    assert run.data.params["seed"] == "0"
    assert run.data.params["epochs"] == "2"
    assert run.data.metrics["macro_f1"] == pytest.approx(0.7)
    assert info.model_version is not None


def test_log_run_registra_a_curva_de_treino_por_epoca(tracking_uri, resultado):
    info = log_run(
        tracking_uri=tracking_uri, experiment="teste",
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        result=resultado, metrics=_metricas(0.7), register_as=MODELO,
    )
    mlflow.set_tracking_uri(tracking_uri)
    historico = MlflowClient().get_metric_history(info.run_id, "train_loss")
    assert len(historico) == 2


def test_sem_alias_nao_ha_campeao(tracking_uri):
    assert load_champion_metrics(tracking_uri=tracking_uri, model_name=MODELO) is None


def test_promove_e_le_as_metricas_do_campeao(tracking_uri, resultado):
    info = log_run(
        tracking_uri=tracking_uri, experiment="teste",
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        result=resultado, metrics=_metricas(0.63), register_as=MODELO,
    )
    promote(tracking_uri=tracking_uri, model_name=MODELO, version=info.model_version)
    campeao = load_champion_metrics(tracking_uri=tracking_uri, model_name=MODELO)
    assert campeao is not None
    assert campeao.macro_f1 == pytest.approx(0.63)


def test_promover_move_o_alias_para_a_nova_versao(tracking_uri, resultado):
    cfg = TrainConfig(seed=0, epochs=2, batch_size=8)
    primeira = log_run(tracking_uri=tracking_uri, experiment="t", config=cfg,
                       result=resultado, metrics=_metricas(0.50), register_as=MODELO)
    promote(tracking_uri=tracking_uri, model_name=MODELO, version=primeira.model_version)
    segunda = log_run(tracking_uri=tracking_uri, experiment="t", config=cfg,
                      result=resultado, metrics=_metricas(0.80), register_as=MODELO)
    promote(tracking_uri=tracking_uri, model_name=MODELO, version=segunda.model_version)

    mlflow.set_tracking_uri(tracking_uri)
    vigente = MlflowClient().get_model_version_by_alias(MODELO, ALIAS_PRODUCAO)
    assert vigente.version == segunda.model_version
    assert load_champion_metrics(
        tracking_uri=tracking_uri, model_name=MODELO
    ).macro_f1 == pytest.approx(0.80)
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/ml/tests/test_tracking.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_ml.tracking'`

- [ ] **Step 3: Implementar**

```python
# packages/ml/src/youfy_ml/tracking.py
from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from .evaluate import Metrics
from .train import TrainConfig, TrainResult

ALIAS_PRODUCAO = "production"
CAMINHO_ARTEFATO = "model"
ARQUIVO_METRICAS = "metrics.json"


@dataclass(frozen=True, slots=True)
class RunInfo:
    run_id: str
    model_version: str | None


def log_run(
    *,
    tracking_uri: str,
    experiment: str,
    config: TrainConfig,
    result: TrainResult,
    metrics: Metrics,
    register_as: str,
) -> RunInfo:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    mlflow.set_experiment(experiment)

    with mlflow.start_run() as run:
        mlflow.log_params({k: str(v) for k, v in asdict(config).items()})
        mlflow.log_param("classes", ",".join(result.classifier.classes))
        mlflow.log_param("feature_fingerprint", result.classifier.feature_spec.fingerprint())

        for epoca in result.history:
            mlflow.log_metric("train_loss", epoca.train_loss, step=epoca.epoch)
            mlflow.log_metric("train_acc", epoca.train_acc, step=epoca.epoch)
            mlflow.log_metric("val_loss", epoca.val_loss, step=epoca.epoch)
            mlflow.log_metric("val_acc", epoca.val_acc, step=epoca.epoch)

        mlflow.log_metrics(metrics.as_flat_dict())

        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / CAMINHO_ARTEFATO
            result.classifier.save(pasta)
            # As metricas viajam junto com o artefato: e assim que o gate le o
            # campeao sem precisar rastrear de qual run ele veio.
            (pasta / ARQUIVO_METRICAS).write_text(json.dumps(asdict(metrics), indent=2))
            mlflow.log_artifacts(str(pasta), artifact_path=CAMINHO_ARTEFATO)

        versao = mlflow.register_model(
            f"runs:/{run.info.run_id}/{CAMINHO_ARTEFATO}", register_as
        )
        return RunInfo(run_id=run.info.run_id, model_version=versao.version)


def promote(*, tracking_uri: str, model_name: str, version: str) -> None:
    mlflow.set_registry_uri(tracking_uri)
    MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri).set_registered_model_alias(
        name=model_name, alias=ALIAS_PRODUCAO, version=version
    )


def load_champion_metrics(*, tracking_uri: str, model_name: str) -> Metrics | None:
    cliente = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    try:
        versao = cliente.get_model_version_by_alias(model_name, ALIAS_PRODUCAO)
    except MlflowException:
        return None

    mlflow.set_tracking_uri(tracking_uri)
    local = mlflow.artifacts.download_artifacts(
        run_id=versao.run_id, artifact_path=f"{CAMINHO_ARTEFATO}/{ARQUIVO_METRICAS}"
    )
    return Metrics(**json.loads(Path(local).read_text()))
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `uv run pytest packages/ml/tests/test_tracking.py -v`
Expected: PASS nos 5 testes

- [ ] **Step 5: Commitar**

```bash
git add packages/ml
git commit -m "feat(ml): tracking no mlflow e registro por alias de producao"
```

---

### Task 8: `serving` — carga do registry com validação de FeatureSpec

**Files:**
- Create: `packages/serving/pyproject.toml`, `packages/serving/src/youfy_serving/__init__.py`
- Create: `packages/serving/src/youfy_serving/errors.py`
- Create: `packages/serving/src/youfy_serving/loader.py`
- Create: `packages/serving/src/youfy_serving/predictor.py`
- Create: `packages/serving/tests/conftest.py`, `packages/serving/tests/test_loader.py`, `packages/serving/tests/test_predictor.py`
- Modify: `pyproject.toml` (membro do workspace)

**Interfaces:**
- Consumes: `TorchGenreClassifier` (Task 1); `ALIAS_PRODUCAO`, `CAMINHO_ARTEFATO` (Task 7); `FeatureSpec` (1A).
- Produces:
  - `NoProductionModel(Exception)`, `FeatureSpecMismatch(Exception)` — em `youfy_serving.errors`.
  - `LoadedModel(classifier, model_version: str)`
  - `load_production(*, tracking_uri: str, model_name: str, expected_spec: FeatureSpec) -> LoadedModel` — **levanta `FeatureSpecMismatch` se a spec do artefato divergir**.
  - `GenrePrediction(distribution: dict[str, float], top_genre: str, model_version: str)`
  - `Predictor(loaded: LoadedModel)` com `predict(melspec: np.ndarray) -> GenrePrediction`

Este é o critério 9 da spec. A validação acontece **na carga**, não na predição:
falha ruidosa na inicialização, nunca degradação silenciosa em produção.

- [ ] **Step 1: Escrever os testes que falham**

```python
# packages/serving/tests/conftest.py
"""Fixture compartilhada pelos dois modulos de teste do `serving`.

Vive no conftest, nao num modulo de teste: importar fixture de um test_*.py
para outro funciona por acidente e obriga a `noqa` espalhado.
"""
import pytest
from youfy_audio.spec import FeatureSpec
from youfy_ml.evaluate import Metrics
from youfy_ml.testing import escrever_features
from youfy_ml.tracking import log_run, promote
from youfy_ml.train import TrainConfig, train

SPEC = FeatureSpec(n_mels=16, n_frames=20)
MODELO = "youfy-genre-clf"


@pytest.fixture
def registry_com_campeao(tmp_path):
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    amostras, classes = escrever_features(
        tmp_path, n_classes=8, por_classe=4, n_mels=16, n_frames=20
    )
    config = TrainConfig(seed=0, epochs=2, batch_size=8)
    resultado = train(
        config, train_samples=amostras, val_samples=amostras,
        features_dir=tmp_path, classes=classes, feature_spec=SPEC,
    )
    info = log_run(
        tracking_uri=uri, experiment="serving", config=config, result=resultado,
        metrics=Metrics(0.7, 0.7, {"g0": 0.7}, [[1]]), register_as=MODELO,
    )
    promote(tracking_uri=uri, model_name=MODELO, version=info.model_version)
    return uri, info.model_version
```

```python
# packages/serving/tests/test_loader.py
import pytest
from youfy_audio.spec import FeatureSpec
from youfy_serving.errors import FeatureSpecMismatch, NoProductionModel
from youfy_serving.loader import load_production

from .conftest import MODELO, SPEC


def test_carrega_o_modelo_sob_o_alias_de_producao(registry_com_campeao):
    uri, versao = registry_com_campeao
    carregado = load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)
    assert carregado.model_version == versao
    assert carregado.classifier.feature_spec == SPEC
    assert len(carregado.classifier.classes) == 8


def test_sem_modelo_promovido_levanta_erro_tipado(tmp_path):
    """Nunca chuta: a ausência de campeão é um estado nomeado."""
    uri = f"sqlite:///{tmp_path / 'vazio.db'}"
    with pytest.raises(NoProductionModel, match=MODELO):
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)


def test_feature_spec_divergente_recusa_carregar(registry_com_campeao):
    """Critério 9 da spec: training/serving skew vira falha na carga.

    Sem isto, um modelo treinado com n_mels=16 servido com 32 não estoura nem
    loga erro — só fica pior em silêncio.
    """
    uri, _ = registry_com_campeao
    divergente = FeatureSpec(n_mels=32, n_frames=20)
    with pytest.raises(FeatureSpecMismatch) as exc:
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=divergente)
    assert divergente.fingerprint() in str(exc.value)
    assert SPEC.fingerprint() in str(exc.value)


def test_divergencia_em_qualquer_campo_e_detectada(registry_com_campeao):
    uri, _ = registry_com_campeao
    for alterada in (
        FeatureSpec(n_mels=16, n_frames=20, hop_length=256),
        FeatureSpec(n_mels=16, n_frames=40),
        FeatureSpec(n_mels=16, n_frames=20, sample_rate=44100),
    ):
        with pytest.raises(FeatureSpecMismatch):
            load_production(tracking_uri=uri, model_name=MODELO, expected_spec=alterada)
```

```python
# packages/serving/tests/test_predictor.py
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
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest packages/serving/tests -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_serving'`

- [ ] **Step 3: Criar o pacote**

```toml
# packages/serving/pyproject.toml
[project]
name = "youfy-serving"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["youfy-audio", "youfy-ml", "numpy>=1.26", "mlflow>=2.13"]

[tool.uv.sources]
youfy-audio = { workspace = true }
youfy-ml = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Acrescente `youfy-serving` ao `pyproject.toml` da raiz, como os demais.

- [ ] **Step 4: Implementar o loader**

```python
# packages/serving/src/youfy_serving/errors.py
class NoProductionModel(Exception):
    """Nao ha versao sob o alias de producao para o modelo pedido."""


class FeatureSpecMismatch(Exception):
    """A FeatureSpec do artefato diverge da config do featurizer."""
```

```python
# packages/serving/src/youfy_serving/loader.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from youfy_audio.spec import FeatureSpec
from youfy_ml.artifact import TorchGenreClassifier
from youfy_ml.tracking import ALIAS_PRODUCAO, CAMINHO_ARTEFATO

from .errors import FeatureSpecMismatch, NoProductionModel


@dataclass(frozen=True, slots=True)
class LoadedModel:
    classifier: TorchGenreClassifier
    model_version: str


def load_production(
    *, tracking_uri: str, model_name: str, expected_spec: FeatureSpec
) -> LoadedModel:
    """Resolve o alias de produção e valida a FeatureSpec embutida no artefato.

    A validação é na carga, de propósito: training/serving skew tem que ser
    falha ruidosa na inicialização, nunca degradação silenciosa na predição.
    """
    cliente = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    try:
        versao = cliente.get_model_version_by_alias(model_name, ALIAS_PRODUCAO)
    except MlflowException as exc:
        raise NoProductionModel(
            f"nenhuma versao sob o alias '{ALIAS_PRODUCAO}' para o modelo '{model_name}'"
        ) from exc

    mlflow.set_tracking_uri(tracking_uri)
    local = mlflow.artifacts.download_artifacts(
        run_id=versao.run_id, artifact_path=CAMINHO_ARTEFATO
    )
    classificador = TorchGenreClassifier.load(Path(local))

    if classificador.feature_spec != expected_spec:
        raise FeatureSpecMismatch(
            "a FeatureSpec do artefato diverge da config do featurizer: "
            f"modelo={classificador.feature_spec.fingerprint()} "
            f"({classificador.feature_spec}) contra "
            f"featurizer={expected_spec.fingerprint()} ({expected_spec})"
        )

    return LoadedModel(classifier=classificador, model_version=versao.version)
```

- [ ] **Step 5: Implementar o preditor**

```python
# packages/serving/src/youfy_serving/predictor.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .loader import LoadedModel


@dataclass(frozen=True, slots=True)
class GenrePrediction:
    distribution: dict[str, float]
    top_genre: str
    model_version: str


class Predictor:
    def __init__(self, loaded: LoadedModel) -> None:
        self._loaded = loaded

    @property
    def model_version(self) -> str:
        return self._loaded.model_version

    def predict(self, melspec: np.ndarray) -> GenrePrediction:
        clf = self._loaded.classifier
        probs = clf.predict(melspec)
        distribuicao = {c: float(p) for c, p in zip(clf.classes, probs)}
        return GenrePrediction(
            distribution=distribuicao,
            top_genre=clf.classes[int(np.argmax(probs))],
            model_version=self._loaded.model_version,
        )
```

- [ ] **Step 6: Rodar os testes e confirmar que passam**

Run: `uv sync --all-extras && uv run pytest packages/serving/tests -v`
Expected: PASS nos 8 testes

- [ ] **Step 7: Commitar**

```bash
git add packages/serving pyproject.toml uv.lock
git commit -m "feat(serving): carga do registry com validacao de featurespec na inicializacao"
```

---

### Task 9: CLI `train` e `evaluate`, e2e do 1B e CI

**Files:**
- Create: `pipelines/src/youfy_pipelines/training.py`
- Modify: `pipelines/src/youfy_pipelines/cli.py`
- Modify: `pipelines/pyproject.toml` (dependências `youfy-ml`, `youfy-serving`)
- Create: `packages/catalog/src/youfy_catalog/queries.py` (o 1A não o criou)
- Create: `pipelines/tests/test_training.py`, `pipelines/tests/test_ciclo_1b_e2e.py`
- Modify: `Makefile`, `.github/workflows/ci.yml`
- Modify: `tests/test_workspace.py` (fronteira dos pacotes novos)

**Interfaces:**
- Consumes: tudo das Tasks 1 a 8; `run_ingest`/`run_featurize`/`run_split`/`splits_dir`/`features_dir` (1A).
- Produces:
  - `labeled_tracks_for(session, *, track_ids: list[str]) -> list[LabeledTrack]` e `known_genres(session) -> list[str]` (em `youfy_catalog.queries`).
  - `load_split(data_dir, spec, nome) -> list[str]`
  - `run_train(session, *, data_dir, spec, config, tracking_uri, model_name, experiment) -> RunInfo`
  - `run_evaluate(session, *, data_dir, spec, tracking_uri, model_name, version) -> PromotionDecision`
  - CLI: `youfy pipeline train`, `youfy pipeline evaluate`

- [ ] **Step 1: Escrever os testes que falham**

```python
# pipelines/tests/test_training.py
import json

from youfy_audio.spec import FeatureSpec
from youfy_catalog.queries import known_genres, labeled_tracks_for
from youfy_catalog.repository import upsert_artist, upsert_track
from youfy_pipelines.training import load_split

SPEC = FeatureSpec(n_mels=16, n_frames=20)


def _semear(session, n=6):
    upsert_artist(session, id="fma:artist:1", name="A", source="fma")
    for i in range(n):
        upsert_track(session, id=f"fma:track:{i}", artist_id="fma:artist:1", title=f"t{i}",
                     duration_ms=1000, audio_path=f"/x{i}.wav",
                     top_genre="Rock" if i % 2 else "Jazz", source="fma")
    session.flush()


def test_labeled_tracks_for_traduz_ids_em_rotulos(session):
    _semear(session)
    rotulados = labeled_tracks_for(session, track_ids=["fma:track:0", "fma:track:1"])
    assert {r.track_id for r in rotulados} == {"fma_track_0", "fma_track_1"}
    assert {r.label for r in rotulados} == {"Jazz", "Rock"}


def test_known_genres_e_ordenado_e_sem_repeticao(session):
    _semear(session)
    assert known_genres(session) == ["Jazz", "Rock"]


def test_known_genres_e_estavel_entre_chamadas(session):
    """A ordem das classes é contrato: instabilidade aqui reordena o vetor de saída."""
    _semear(session)
    assert known_genres(session) == known_genres(session)


def test_load_split_le_o_arquivo_do_fingerprint(tmp_path):
    destino = tmp_path / "splits" / SPEC.fingerprint()
    destino.mkdir(parents=True)
    (destino / "train.json").write_text(
        json.dumps({"seed": 42, "fingerprint": SPEC.fingerprint(),
                    "track_ids": ["fma:track:1", "fma:track:2"]})
    )
    assert load_split(tmp_path, SPEC, "train") == ["fma:track:1", "fma:track:2"]
```

```python
# pipelines/tests/test_ciclo_1b_e2e.py
"""Fecha o ciclo: acervo → features → split → treino → gate → serving.

É o teste que prova que os artefatos do 1A alimentam o 1B sem adaptador.
"""
import numpy as np
import pytest
from youfy_audio.spec import FeatureSpec
from youfy_catalog.testing import FixtureTrack, build_fma_fixture
from youfy_ml.train import TrainConfig
from youfy_pipelines.featurize import run_featurize
from youfy_pipelines.ingest import run_ingest
from youfy_pipelines.split import run_split
from youfy_pipelines.training import run_evaluate, run_train
from youfy_serving.errors import FeatureSpecMismatch, NoProductionModel
from youfy_serving.loader import load_production
from youfy_serving.predictor import Predictor

SPEC = FeatureSpec(n_mels=16, n_frames=20)
MODELO = "youfy-genre-clf"
GENEROS = ["Rock", "Jazz", "Folk"]

# O e2e passa `floor=0.0` de proposito: a promocao precisa ser deterministica
# para que as assercoes seguintes sempre rodem. O piso e a margem tem cobertura
# exaustiva na Task 6, onde sao funcao pura.
PISO_E2E = 0.0


@pytest.fixture
def acervo(session, tmp_path):
    faixas = []
    tid = 2
    for g, genero in enumerate(GENEROS):
        for a in range(10):
            for _ in range(3):
                faixas.append(FixtureTrack(tid, g * 100 + a, f"Artista {g}-{a}", genero))
                tid += 1
    build_fma_fixture(tmp_path, faixas)
    run_ingest(session, dump_dir=tmp_path, subset="small", audio_ext=".wav")
    session.flush()
    run_featurize(session, data_dir=tmp_path / "data", spec=SPEC)
    session.flush()
    run_split(session, data_dir=tmp_path / "data", spec=SPEC, seed=42)
    return tmp_path / "data", f"sqlite:///{tmp_path / 'mlflow.db'}"


def test_serving_antes_do_primeiro_treino_recusa_de_forma_tipada(acervo):
    _, uri = acervo
    with pytest.raises(NoProductionModel):
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)


def test_ciclo_completo_treina_promove_e_serve(session, acervo):
    data_dir, uri = acervo

    info = run_train(
        session, data_dir=data_dir, spec=SPEC,
        config=TrainConfig(seed=0, epochs=3, batch_size=8),
        tracking_uri=uri, model_name=MODELO, experiment="e2e",
    )
    assert info.model_version is not None

    decisao = run_evaluate(
        session, data_dir=data_dir, spec=SPEC, tracking_uri=uri,
        model_name=MODELO, version=info.model_version, floor=PISO_E2E,
    )
    assert decisao.champion_f1 is None  # primeiro modelo: o criterio e o piso
    assert decisao.promote is True

    preditor = Predictor(
        load_production(tracking_uri=uri, model_name=MODELO, expected_spec=SPEC)
    )
    p = preditor.predict(np.zeros((16, 20), dtype=np.float32))
    assert p.model_version == info.model_version
    assert set(p.distribution) == set(GENEROS)
    assert np.isclose(sum(p.distribution.values()), 1.0, atol=1e-5)


def test_featurizer_divergente_derruba_o_serving_na_carga(session, acervo):
    """Critério 9 no encadeamento real, não só no unitário."""
    data_dir, uri = acervo
    info = run_train(
        session, data_dir=data_dir, spec=SPEC,
        config=TrainConfig(seed=0, epochs=2, batch_size=8),
        tracking_uri=uri, model_name=MODELO, experiment="e2e",
    )
    decisao = run_evaluate(
        session, data_dir=data_dir, spec=SPEC, tracking_uri=uri,
        model_name=MODELO, version=info.model_version, floor=PISO_E2E,
    )
    assert decisao.promote is True

    with pytest.raises(FeatureSpecMismatch):
        load_production(
            tracking_uri=uri, model_name=MODELO,
            expected_spec=FeatureSpec(n_mels=32, n_frames=20),
        )
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `uv run pytest pipelines/tests/test_training.py pipelines/tests/test_ciclo_1b_e2e.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'youfy_pipelines.training'`

- [ ] **Step 3: Acrescentar as consultas ao catálogo**

```python
# packages/catalog/src/youfy_catalog/queries.py
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Track


@dataclass(frozen=True, slots=True)
class LabeledTrackRow:
    track_id: str
    label: str


def labeled_tracks_for(session: Session, *, track_ids: list[str]) -> list[LabeledTrackRow]:
    """Traduz ids do catálogo em `(nome de arquivo de feature, rótulo)`.

    O `:` do id vira `_`, casando com o nome que o estágio `featurize` grava.
    """
    linhas = session.execute(
        select(Track.id, Track.top_genre)
        .where(Track.id.in_(track_ids))
        .where(Track.top_genre.is_not(None))
        .order_by(Track.id)
    ).all()
    return [LabeledTrackRow(tid.replace(":", "_"), genero) for tid, genero in linhas]


def known_genres(session: Session) -> list[str]:
    """Ordem canônica das classes: ordenada, para nunca depender de inserção."""
    linhas = session.execute(
        select(Track.top_genre).where(Track.top_genre.is_not(None)).distinct()
    ).scalars().all()
    return sorted(linhas)
```

- [ ] **Step 4: Implementar a ponte em `pipelines`**

```python
# pipelines/src/youfy_pipelines/training.py
from __future__ import annotations

import json
from pathlib import Path

import structlog
from sqlalchemy.orm import Session
from youfy_audio.spec import FeatureSpec
from youfy_catalog.queries import known_genres, labeled_tracks_for
from youfy_ml.dataset import LabeledTrack
from youfy_ml.evaluate import evaluate
from youfy_ml.promotion import PromotionDecision, should_promote
from youfy_ml.tracking import RunInfo, load_champion_metrics, log_run, promote
from youfy_ml.train import TrainConfig, train
from youfy_serving.loader import carregar_versao

from .featurize import features_dir
from .split import splits_dir

log = structlog.get_logger()


def load_split(data_dir: Path, spec: FeatureSpec, nome: str) -> list[str]:
    arquivo = splits_dir(data_dir, spec) / f"{nome}.json"
    return json.loads(arquivo.read_text())["track_ids"]


def _amostras(session: Session, data_dir: Path, spec: FeatureSpec, nome: str) -> list[LabeledTrack]:
    ids = load_split(data_dir, spec, nome)
    return [LabeledTrack(r.track_id, r.label) for r in labeled_tracks_for(session, track_ids=ids)]


def run_train(
    session: Session,
    *,
    data_dir: Path,
    spec: FeatureSpec,
    config: TrainConfig,
    tracking_uri: str,
    model_name: str,
    experiment: str = "youfy-genre",
) -> RunInfo:
    classes = known_genres(session)
    resultado = train(
        config,
        train_samples=_amostras(session, data_dir, spec, "train"),
        val_samples=_amostras(session, data_dir, spec, "val"),
        features_dir=features_dir(data_dir, spec),
        classes=classes,
        feature_spec=spec,
    )
    metricas = evaluate(
        resultado.classifier,
        samples=_amostras(session, data_dir, spec, "val"),
        features_dir=features_dir(data_dir, spec),
    )
    info = log_run(
        tracking_uri=tracking_uri, experiment=experiment, config=config,
        result=resultado, metrics=metricas, register_as=model_name,
    )
    log.info("train.concluido", run_id=info.run_id, versao=info.model_version,
             val_macro_f1=round(metricas.macro_f1, 4))
    return info


def run_evaluate(
    session: Session,
    *,
    data_dir: Path,
    spec: FeatureSpec,
    tracking_uri: str,
    model_name: str,
    version: str,
    margin: float = 0.005,
    floor: float = 0.40,
) -> PromotionDecision:
    """Avalia no split de teste e aplica o gate. Não promover é sucesso, não erro."""
    classificador = carregar_versao(
        tracking_uri=tracking_uri, model_name=model_name, version=version, expected_spec=spec
    )
    desafiante = evaluate(
        classificador,
        samples=_amostras(session, data_dir, spec, "test"),
        features_dir=features_dir(data_dir, spec),
    )
    campeao = load_champion_metrics(tracking_uri=tracking_uri, model_name=model_name)
    decisao = should_promote(desafiante, campeao, margin=margin, floor=floor)

    if decisao.promote:
        promote(tracking_uri=tracking_uri, model_name=model_name, version=version)

    log.info("evaluate.concluido", promoveu=decisao.promote, motivo=decisao.reason,
             desafiante=round(decisao.challenger_f1, 4))
    return decisao
```

Acrescente ao `loader.py` da Task 8 a função que carrega uma versão nomeada, que o
gate precisa para avaliar o desafiante antes de ele ser campeão:

```python
# packages/serving/src/youfy_serving/loader.py — acrescentar

def carregar_versao(
    *, tracking_uri: str, model_name: str, version: str, expected_spec: FeatureSpec
) -> TorchGenreClassifier:
    """Carrega uma versão específica, sem passar pelo alias de produção."""
    cliente = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
    versao = cliente.get_model_version(model_name, version)
    mlflow.set_tracking_uri(tracking_uri)
    local = mlflow.artifacts.download_artifacts(
        run_id=versao.run_id, artifact_path=CAMINHO_ARTEFATO
    )
    classificador = TorchGenreClassifier.load(Path(local))
    if classificador.feature_spec != expected_spec:
        raise FeatureSpecMismatch(
            f"versao {version}: modelo={classificador.feature_spec.fingerprint()} "
            f"contra featurizer={expected_spec.fingerprint()}"
        )
    return classificador
```

Acrescente `youfy-ml` e `youfy-serving` às `dependencies` e ao `[tool.uv.sources]`
de `pipelines/pyproject.toml`.

- [ ] **Step 5: Acrescentar os comandos à CLI**

```python
# pipelines/src/youfy_pipelines/cli.py — acrescentar

from youfy_ml.train import TrainConfig

from .training import run_evaluate, run_train


@pipeline.command("train")
def train_cmd(
    data_dir: Path = typer.Option(None),
    seed: int = typer.Option(42),
    epochs: int = typer.Option(10),
    batch_size: int = typer.Option(32),
    lr: float = typer.Option(1e-3),
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
    tracking_uri: str = typer.Option("http://localhost:5000"),
    model_name: str = typer.Option("youfy-genre-clf"),
) -> None:
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    config = TrainConfig(seed=seed, epochs=epochs, batch_size=batch_size, lr=lr)
    with session_scope() as session:
        info = run_train(session, data_dir=raiz, spec=spec, config=config,
                         tracking_uri=tracking_uri, model_name=model_name)
    typer.echo(f"run_id={info.run_id} versao={info.model_version}")


@pipeline.command("evaluate")
def evaluate_cmd(
    version: str = typer.Option(..., help="Versao registrada a avaliar."),
    data_dir: Path = typer.Option(None),
    n_mels: int = typer.Option(128),
    hop_length: int = typer.Option(512),
    n_frames: int = typer.Option(1292),
    tracking_uri: str = typer.Option("http://localhost:5000"),
    model_name: str = typer.Option("youfy-genre-clf"),
    margin: float = typer.Option(0.005),
    floor: float = typer.Option(0.40),
) -> None:
    """Nao promover e resultado valido: sai com codigo 0 e relata o motivo."""
    configure_logging()
    raiz = data_dir or Settings().data_dir
    spec = FeatureSpec(n_mels=n_mels, hop_length=hop_length, n_frames=n_frames)
    with session_scope() as session:
        decisao = run_evaluate(session, data_dir=raiz, spec=spec, tracking_uri=tracking_uri,
                               model_name=model_name, version=version,
                               margin=margin, floor=floor)
    typer.echo(f"promoveu={decisao.promote} motivo={decisao.reason}")
```

- [ ] **Step 6: Estender o teste de fronteira e o Makefile**

```python
# tests/test_workspace.py — acrescentar

def test_ml_nao_importa_catalog_serving_nem_pipelines():
    """`ml` treina a partir de um diretorio de arrays; nao conhece banco nem HTTP."""
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[1] / "packages/ml/src"
    fontes = "\n".join(p.read_text() for p in raiz.rglob("*.py"))
    for proibido in ("youfy_catalog", "youfy_serving", "youfy_pipelines"):
        assert proibido not in fontes


def test_serving_nao_importa_catalog_nem_pipelines():
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[1] / "packages/serving/src"
    fontes = "\n".join(p.read_text() for p in raiz.rglob("*.py"))
    for proibido in ("youfy_catalog", "youfy_pipelines"):
        assert proibido not in fontes
```

```makefile
# Makefile — acrescentar, e incluir em .PHONY

train:
	uv run youfy pipeline train

evaluate:
	uv run youfy pipeline evaluate --version $(VERSION)

e2e-1b:
	uv run pytest pipelines/tests/test_ciclo_1b_e2e.py -v --durations=5
```

- [ ] **Step 7: Rodar tudo e acrescentar ao CI**

```yaml
# .github/workflows/ci.yml — acrescentar depois do e2e do 1A
      - run: uv run pytest pipelines/tests/test_ciclo_1b_e2e.py -v --durations=5
```

Run: `make lint && make test && make e2e && make e2e-1b`
Expected: lint limpo; toda a suíte verde; os dois e2e passando

- [ ] **Step 8: Commitar**

```bash
git add pipelines packages/catalog packages/serving tests Makefile .github pyproject.toml uv.lock
git commit -m "feat(pipelines): comandos train e evaluate fechando o ciclo ate o serving"
```

---

## Verificação final do plano 1B

Numa máquina limpa, com o Postgres e o MLflow no ar:

```bash
make setup && make up && make mlflow-up
make lint && make test && make e2e && make e2e-1b
```

E, com o acervo real do 1A já ingerido e featurizado:

```bash
youfy pipeline train --seed 42 --epochs 30
youfy pipeline evaluate --version 1
```

Mapeamento para os critérios de aceite da spec (§10): este plano cobre os itens
**4, 5, 9, 11 e 12**. Restam para o 1C os itens 6, 7, 8 e 10 — TUI, buffer
offline de eventos, endpoint `/genre` com 503, e o teste ponta a ponta em CI
abaixo de dois minutos.

## O que o 1C vai consumir daqui

- `Predictor` e `GenrePrediction` — o endpoint `/tracks/{id}/genre` é um invólucro fino disso.
- `NoProductionModel` — é o que a API traduz em **503 explícito**, nunca em fallback silencioso.
- `load_production(expected_spec=...)` — a API a chama na inicialização, e **falha ao subir** se divergir.
- `ALIAS_PRODUCAO` e `model_version` — a `model_version` vai para `predictions` e para `/health`.
