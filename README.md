<div align="center">

<img src="docs/assets/banner.svg" alt="Youfy Banner" width="100%" />

# Youfy

**Closed-Loop Music Intelligence & MLOps Platform**

[![CI](https://github.com/Oseiasdfarias/youfy/actions/workflows/ci.yml/badge.svg)](https://github.com/Oseiasdfarias/youfy/actions/workflows/ci.yml)
[![Documentation](https://github.com/Oseiasdfarias/youfy/actions/workflows/deploy-docs.yml/badge.svg)](https://oseiasdfarias.github.io/youfy/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-black.svg?style=flat&logo=python)](https://www.python.org/)
[![DVC](https://img.shields.io/badge/data_versioning-DVC-black.svg?style=flat&logo=dvc)](https://dvc.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg?style=flat)](LICENSE)

[📖 **Documentação Online**](https://oseiasdfarias.github.io/youfy/) • [Arquitetura](https://oseiasdfarias.github.io/youfy/arquitetura/decisoes/) • [Contratos](https://oseiasdfarias.github.io/youfy/arquitetura/contratos/) • [Guia Rápido](https://oseiasdfarias.github.io/youfy/guia/inicio-rapido/)

</div>

---

## Sobre o Projeto

O **Youfy** é um laboratório de IA aplicada no formato de um ecossistema musical de alta fidelidade. O produto existe para dar carga real aos modelos em produção; os modelos e seu ciclo de vida (MLOps) são o objetivo central.

- **Catálogo Aberto:** Ingestão estruturada do benchmark acadêmico **Free Music Archive (FMA)** (~8.000 clipes, 8 gêneros balanceados).
- **Invariante de Artista Testado:** Particionamento estratificado com garantia matemática e testes de propriedade (Hypothesis) de disjunção estrita ($\text{artistas}(\text{train}) \cap \text{artistas}(\text{test}) = \emptyset$).
- **Cache por Fingerprint:** Mel-espectrogramas armazenados sob hash SHA-256 da `FeatureSpec`, eliminando *training/serving skew* e permitindo invalidação de cache por diretório.
- **Rastreabilidade DVC:** Matrizes binárias `.npy` versionadas com DVC e remote configurado.
- **Observabilidade Magra:** Logs em JSON estruturado com `structlog`.

---

## Começando

### 1. Pré-requisitos
- Python 3.11+
- `uv` (gerenciador de dependências)
- Docker & Docker Compose

### 2. Instalação e Testes

```bash
# Configura o workspace monorepo com lockfile determinístico
make setup

# Inicializa o Postgres 16 local (porta 5433)
make up

# Executa a suíte de testes unitários e de integração (45 testes)
make test

# Executa o pipeline ponta a ponta sobre micro-dataset
make e2e

# Executa checagem de linter
make lint
```

### 3. Documentação Local

```bash
# Servidor local de documentação com live-reload (http://localhost:8000)
make docs-serve

# Build estrito da documentação
make docs-build
```

---

## Pipeline Offline (CLI Typer)

```bash
# 1. Ingestão com quarentena automática de áudios corrompidos
youfy pipeline ingest --dump-dir ./data/raw/fma --subset small

# 2. Featurização retomável (gera .npy e _manifest.json por fingerprint)
youfy pipeline featurize --n-mels 128 --hop-length 512

# 3. Particionamento determinístico por artista
youfy pipeline split --seed 42
```

---

## Estrutura do Monorepo

```
youfy/
├── packages/
│   ├── audio/           # DSP e extração de melspec (funções puras sobre arrays)
│   └── catalog/         # Modelos SQLAlchemy 2.0, migrations Alembic e parser FMA
├── pipelines/           # CLI Typer 'youfy' e estágios offline
├── docs/                # Documentação técnica MkDocs e especificações de engenharia
└── data/                # Features (.npy) e splits (.json) rastreados por DVC
```

---

## Licença

Distribuído sob a licença MIT. Consulte a documentação para mais detalhes.
